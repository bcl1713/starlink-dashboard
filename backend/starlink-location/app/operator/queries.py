"""Complete saved reads and acceptance-sequence snapshot pagination."""

import base64
import hashlib
import json
from uuid import UUID

from .errors import OperatorError
from .models import HistoryPage, RecordPage, SavedRecord


def decode_record(row, columns):
    data = dict(zip(columns, row))
    for field in ("author", "time", "provenance", "payload"):
        data[field] = json.loads(data.pop(field + "_json"))
    data["deleted"] = bool(data["deleted"])
    return SavedRecord.model_validate(data)


def select_records(connection, sql, parameters=()):
    result = connection.execute(sql, parameters)
    columns = [column[0] for column in result.description]
    return [decode_record(row, columns) for row in result.fetchall()]


def get_record(connection, record_id):
    records = select_records(
        connection, "SELECT * FROM current_records WHERE record_id=?", (str(record_id),)
    )
    if not records:
        raise OperatorError("record_not_found")
    return records[0]


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _encode(value):
    return base64.urlsafe_b64encode(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).decode()


def page(connection, *, identity, clock, kind, filters, limit=50, cursor=None):
    if type(limit) is not int or not 1 <= limit <= 200:
        raise OperatorError("validation_error", fields={"limit": "Expected 1 to 200"})
    fingerprint = _digest({"kind": kind, "filters": filters})
    maximum = connection.execute(
        "SELECT coalesce(max(journal_seq), 0) FROM revisions"
    ).fetchone()[0]
    if cursor is None:
        state = {
            "v": 1,
            "store": str(identity.store_id),
            "epoch": str(identity.api_epoch),
            "H": maximum,
            "filter": fingerprint,
            "last": "" if kind == "records" else 0,
            "as_of": clock.now().isoformat(),
        }
    else:
        try:
            state = json.loads(base64.b64decode(cursor, altchars=b"-_", validate=True))
            if (
                set(state) != {"v", "store", "epoch", "H", "filter", "last", "as_of"}
                or state["v"] != 1
                or state["store"] != str(identity.store_id)
                or state["epoch"] != str(identity.api_epoch)
                or state["filter"] != fingerprint
                or type(state["H"]) is not int
                or not 0 <= state["H"] <= maximum
                or (kind == "records" and not isinstance(state["last"], str))
                or (
                    kind != "records"
                    and (type(state["last"]) is not int or state["last"] < 0)
                )
            ):
                raise ValueError("Invalid snapshot")
            from .time_models import utc_timestamp

            utc_timestamp(state["as_of"])
            if kind == "records" and str(UUID(state["last"])) != state["last"]:
                raise ValueError("Invalid record boundary")
        except (ValueError, TypeError, KeyError, UnicodeError) as error:
            raise OperatorError(
                "validation_error", fields={"cursor": "Invalid cursor"}
            ) from error
    args = [state["H"]]
    if kind == "records":
        sql = (
            "WITH chosen AS (SELECT record_id, max(journal_seq) AS seq FROM revisions "
            "WHERE journal_seq<=? GROUP BY record_id) SELECT v.* FROM revisions v "
            "JOIN chosen c ON v.journal_seq=c.seq WHERE v.record_id>?"
        )
        args.append(state["last"])
        for name in ("mission_id", "scope", "leg_id", "record_type"):
            if filters.get(name) is not None:
                sql += f" AND v.{name}=?"
                args.append(filters[name])
        if not filters.get("include_removed"):
            sql += " AND v.deleted=0"
        sql += " ORDER BY v.record_id"
    else:
        field = "record_id" if kind == "history" else "mission_id"
        sql = f"SELECT * FROM revisions WHERE journal_seq<=? AND {field}=? AND journal_seq>? ORDER BY journal_seq"
        args.extend([filters[field], state["last"]])
    sql += " LIMIT ?"
    args.append(limit + 1)
    records = select_records(connection, sql, args)
    more = len(records) > limit
    records = records[:limit]
    next_cursor = None
    if more:
        state["last"] = (
            str(records[-1].record_id) if kind == "records" else records[-1].journal_seq
        )
        next_cursor = _encode(state)
    page_type = RecordPage if kind == "records" else HistoryPage
    return page_type(
        items=records, H=state["H"], as_of=state["as_of"], cursor=next_cursor
    )
