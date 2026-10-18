"""Material notification generations; forecast refreshes are not journal entries."""

import hashlib
import json

from .event_models import OperationalEvent
from .time_models import utc_timestamp


def identity(*parts):
    return hashlib.sha256(
        json.dumps(parts, sort_keys=True, default=str).encode()
    ).hexdigest()


def reconcile(connection, events, *, as_of, policy, stability=None):
    events = [event.model_copy(deep=True) for event in events]
    if stability is not None:
        stability.prepare(connection, events, as_of=as_of, policy=policy)
    result = []
    recorded_at = as_of.isoformat()
    for original in events:
        event = original.model_copy(deep=True)
        if stability is not None and event.provenance == "modeled":
            stability.select(connection, event, as_of=as_of, policy=policy)
        occurrence = identity(event.mission_id, event.event_id, event.schedule_key)
        head = connection.execute(
            "SELECT occurrence_id, retired FROM event_heads WHERE event_id=?",
            (event.event_id,),
        ).fetchone()
        if head and (head[0] != occurrence or not event.active) and not head[1]:
            connection.execute(
                "UPDATE event_heads SET retired=1 WHERE event_id=?", (event.event_id,)
            )
            connection.execute(
                "INSERT OR IGNORE INTO event_transitions (occurrence_id,state,recorded_at) VALUES (?, 'retired', ?)",
                (head[0], recorded_at),
            )
        if not event.active:
            event.notification.retired = True
            result.append(event)
            continue
        known = connection.execute(
            "SELECT 1 FROM event_occurrences WHERE occurrence_id=?", (occurrence,)
        ).fetchone()
        if not known:
            connection.execute(
                "INSERT INTO event_occurrences VALUES (?, ?, ?, ?, ?, ?)",
                (
                    occurrence,
                    event.event_id,
                    event.mission_id,
                    event.due_at.isoformat() if event.due_at else None,
                    recorded_at,
                    event.model_dump_json(),
                ),
            )
            connection.execute(
                "INSERT INTO event_transitions (occurrence_id,state,recorded_at) VALUES (?, 'accepted', ?)",
                (occurrence, recorded_at),
            )
        tier = event.notification.severity_generation
        if (
            event.notification.available
            and not connection.execute(
                "SELECT 1 FROM event_tiers WHERE occurrence_id=? AND severity_generation=?",
                (occurrence, tier),
            ).fetchone()
        ):
            connection.execute(
                "INSERT INTO event_tiers VALUES (?, ?, ?)",
                (occurrence, tier, recorded_at),
            )
        retired = bool(
            connection.execute(
                "SELECT 1 FROM event_transitions WHERE occurrence_id=? AND state='retired'",
                (occurrence,),
            ).fetchone()
        )
        if not head or head != (occurrence, int(retired)):
            connection.execute(
                "INSERT INTO event_heads VALUES (?, ?, ?) ON CONFLICT(event_id) DO UPDATE SET occurrence_id=excluded.occurrence_id, retired=excluded.retired",
                (event.event_id, occurrence, int(retired)),
            )
        event.notification.generation = occurrence
        event.notification.retired = retired
        ack = connection.execute(
            "SELECT acknowledged_at FROM event_acknowledgments WHERE occurrence_id=? AND severity_generation>=? ORDER BY severity_generation LIMIT 1",
            (occurrence, event.notification.severity_generation),
        ).fetchone()
        if ack:
            event.notification.acknowledged = True
            event.notification.acknowledged_at = utc_timestamp(ack[0])
        result.append(OperationalEvent.model_validate(event.model_dump()))
    return result
