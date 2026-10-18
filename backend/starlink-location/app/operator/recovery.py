"""Read-only semantic validation and explicit, offline whole-store restoration."""

import json
import os
import shutil
import sqlite3
from contextlib import closing
from uuid import uuid4

from pydantic import ValidationError

from .errors import OperatorError
from .event_models import AckReceipt, OperationalEvent
from .maintenance import admission, bounded, storage_error
from .models import CommandReceipt
from .queries import decode_document, decode_record, select_records
from .references import derive_links, validate_dependencies
from .schema import apply_migrations, validate_integrity
from .time_models import utc_timestamp


def validate_connection(connection, *, clock, allow_legacy=False):
    """Verify complete typed revision chains, receipt bodies and derived links."""
    with bounded(connection) as check:
        apply_migrations(connection, clock=clock, allow_legacy=allow_legacy)
        validate_integrity(connection)
        cursor = connection.execute("SELECT * FROM revisions ORDER BY journal_seq")
        columns = [column[0] for column in cursor.description]
        try:
            for row in cursor:
                check()
                decode_record(row, columns)
            for command_id, status, body in connection.execute(
                "SELECT command_id, response_status, response_json FROM commands"
            ):
                check()
                if json.loads(body).get("receipt_type") == "event_acknowledgment":
                    receipt = AckReceipt.model_validate_json(body)
                    ack = connection.execute(
                        "SELECT occurrence_id, severity_generation, acknowledged_at FROM event_acknowledgments WHERE acknowledgment_id=?",
                        (str(receipt.acknowledgment_id),),
                    ).fetchone()
                    if (
                        str(receipt.command_id) != command_id
                        or status != 200
                        or not ack
                        or ack[:2]
                        != (receipt.occurrence_id, receipt.severity_generation)
                        or receipt.acknowledged_at != utc_timestamp(ack[2])
                        or connection.execute(
                            "SELECT 1 FROM revisions WHERE command_id=?", (command_id,)
                        ).fetchone()
                    ):
                        raise OperatorError("store_corrupt")
                    continue
                receipt = CommandReceipt.model_validate_json(body)
                revisions = select_records(
                    connection,
                    "SELECT * FROM revisions WHERE command_id=? ORDER BY journal_seq",
                    (command_id,),
                )
                if (
                    str(receipt.command_id) != command_id
                    or receipt.response_status != status
                    or receipt.saved_records != revisions
                ):
                    raise OperatorError("store_corrupt")
                raw = connection.execute(
                    "SELECT * FROM revisions WHERE command_id=? ORDER BY journal_seq",
                    (command_id,),
                )
                raw_columns = [column[0] for column in raw.description]
                expected = {
                    "schema_version": 1,
                    "command_id": command_id,
                    "saved_records": [
                        decode_document(row, raw_columns) for row in raw.fetchall()
                    ],
                }
                if receipt.canonical_response != expected:
                    raise OperatorError("store_corrupt")
            version = connection.execute(
                "SELECT max(version) FROM schema_migrations"
            ).fetchone()[0]
            if version >= 2:
                for occurrence_id, event_json in connection.execute(
                    "SELECT occurrence_id, event_json FROM event_occurrences"
                ):
                    OperationalEvent.model_validate_json(event_json)
                    if not connection.execute(
                        "SELECT 1 FROM event_transitions WHERE occurrence_id=? AND state='accepted'",
                        (occurrence_id,),
                    ).fetchone():
                        raise OperatorError("store_corrupt")
            expected_links = set()
            for record in select_records(connection, "SELECT * FROM current_records"):
                check()
                expected_links.update(derive_links(record))
                validate_dependencies(connection, record)
            if expected_links != set(connection.execute("SELECT * FROM current_links")):
                raise OperatorError("store_corrupt")
        except (ValidationError, ValueError, TypeError, KeyError) as error:
            raise OperatorError("store_corrupt") from error
        except OperatorError as error:
            if error.code == "dependency_conflict":
                raise OperatorError("store_corrupt") from error
            raise


def verify_store(store):
    try:
        with admission(store.settings, exclusive=True):
            store._check_identity()
            store._verify()
    except (OperatorError, sqlite3.Error, OSError) as error:
        error = error if isinstance(error, OperatorError) else storage_error(error)
        if not error.retryable:
            store._ready = False
            store._error_code = error.code
        return store.health().model_copy(
            update={"ready": False, "error_code": error.code}
        )
    return store.health()


def restore_store(settings, *, manifest, clock):
    from .backup import checksum, validated_backup
    from .store import OperatorStore, _sync_directory, _write_marker

    if not settings.enabled:
        raise OperatorError("store_unavailable")
    directory = settings.database_path.parent
    with admission(settings, exclusive=True):
        info, source = validated_backup(manifest, clock=clock)
        identity = json.loads(settings.identity_path.read_text())
        if (info["store_id"], info["source_mode"], info["simulation_run_id"]) != (
            identity["store_id"],
            settings.source_mode,
            settings.simulation_run_id,
        ):
            raise OperatorError("store_identity_mismatch")
        # Copy and validate before changing any live file. Pending identity makes
        # an interrupted multi-file replacement fail closed on the next startup.
        scratch = directory / ("restore-" + str(uuid4()) + ".pending")
        preserved = directory / ("preserved-" + str(uuid4()))
        try:
            shutil.copyfile(source, scratch)
            os.chmod(scratch, 0o600)
            with scratch.open("rb") as handle:
                os.fsync(handle.fileno())
            if checksum(scratch) != info["checksum"]:
                raise OperatorError("backup_checksum_mismatch")
            old_h = None
            try:
                from .wal import validate_wal

                validate_wal(settings.database_path)
                with closing(
                    sqlite3.connect(
                        settings.database_path.resolve().as_uri() + "?mode=ro",
                        uri=True,
                        timeout=2,
                    )
                ) as previous, bounded(previous):
                    old_h = previous.execute(
                        "SELECT coalesce(max(journal_seq), 0) FROM revisions"
                    ).fetchone()[0]
            except (sqlite3.Error, OperatorError):
                pass
            preserved.mkdir(mode=0o700)
            preserved_identity = preserved / settings.identity_path.name
            shutil.copyfile(settings.identity_path, preserved_identity)
            os.chmod(preserved_identity, 0o600)
            with preserved_identity.open("rb") as handle:
                os.fsync(handle.fileno())
            _sync_directory(preserved)
            identity.update(api_epoch=str(uuid4()), status="restoring")
            _write_marker(settings.identity_path, identity, first=False)
            for suffix in ("", "-wal", "-shm"):
                path = settings.database_path.with_name(
                    settings.database_path.name + suffix
                )
                if path.exists():
                    os.replace(path, preserved / path.name)
            _sync_directory(preserved)
            os.replace(scratch, settings.database_path)
            _sync_directory(directory)
            candidate = OperatorStore(settings, clock)
            # _verify requires a ready marker, so validate the candidate first.
            connection = candidate._connection()
            try:
                validate_connection(connection, clock=clock)
            finally:
                connection.close()
            report = {
                "restored_H": info["H"],
                "previous_H": old_h,
                "backup_created_at": info["created_at"],
                "preserved": preserved.name,
                "api_epoch": identity["api_epoch"],
            }
            report_path = directory / "restore-report.json"
            _write_marker(report_path, report, first=not report_path.exists())
            identity["status"] = "ready"
            _write_marker(settings.identity_path, identity, first=False)
            candidate._verify()
            candidate._ready = True
            return candidate.health()
        except (sqlite3.Error, OSError) as error:
            raise storage_error(error) from error
        finally:
            scratch.unlink(missing_ok=True)
