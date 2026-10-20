"""Explicit backed-up upgrade under exclusive Operator maintenance admission."""

from .backup import backup_store
from .maintenance import admission
from .schema import apply_migrations
from .store import OperatorStore


def upgrade_store(settings, *, clock):
    store = OperatorStore.open(
        settings, initialize=False, clock=clock, allow_legacy=True
    )
    try:
        with admission(settings, exclusive=True):
            store._check_identity()
            manifest = backup_store(
                store,
                directory=settings.database_path.parent / "pre-upgrade-backups",
                admitted=True,
            )
            connection = store._connection()
            try:
                connection.execute("PRAGMA foreign_keys=OFF")
                connection.execute("BEGIN IMMEDIATE")
                apply_migrations(connection, clock=clock, upgrade=True)
                from .recovery import validate_connection

                validate_connection(connection, clock=clock)
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
            finally:
                connection.execute("PRAGMA foreign_keys=ON")
                connection.close()
            store._allow_legacy = False
            store._verify()
            return manifest
    finally:
        store.close()
