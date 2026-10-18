"""Transient stability candidates; accepted notification anchors stay durable."""

import json
from collections import Counter

from .event_ledger import identity
from .time_models import utc_timestamp


class ModelStability:
    def __init__(self):
        self.candidates = {}

    def prepare(self, connection, events, *, as_of, policy):
        """Match uniquely overlapping occurrences; ambiguous topology waits."""
        old = [
            json.loads(row[0])
            for row in connection.execute(
                "SELECT o.event_json FROM event_heads h JOIN event_occurrences o USING (occurrence_id) WHERE h.retired=0"
            )
        ]
        restrictions = [
            e
            for e in events
            if e.active
            and e.kind == "restriction"
            and e.family_key
            and e.due_at
            and e.end_at
        ]
        matches = {}
        for event in restrictions:
            matches[id(event)] = [
                previous
                for previous in old
                if previous.get("family_key") == event.family_key
                and previous.get("due_at")
                and previous.get("end_at")
                and utc_timestamp(previous["due_at"]) < event.end_at
                and utc_timestamp(previous["end_at"]) > event.due_at
            ]
        uses = Counter(
            previous["event_id"] for group in matches.values() for previous in group
        )
        for event in restrictions:
            group = matches[id(event)]
            if len(group) == 1 and uses[group[0]["event_id"]] == 1:
                event.event_id = group[0]["event_id"]
            elif group:
                family = sorted(
                    [e for e in restrictions if e.family_key == event.family_key],
                    key=lambda e: (e.due_at, e.end_at),
                )
                ordinal = next(
                    index for index, item in enumerate(family) if item is event
                )
                key = "topology:" + identity(event.family_key, len(family), ordinal)
                candidate = self.candidates.get(key)
                if candidate is None or as_of < candidate[1]:
                    candidate = ((event.due_at, event.end_at), as_of, 1)
                elif (
                    as_of - candidate[1]
                ).total_seconds() >= policy.model_capture_spacing_seconds:
                    candidate = (candidate[0], as_of, candidate[2] + 1)
                self._remember(key, candidate)
                event.event_id = identity(
                    event.family_key, "reshaped", candidate[0], ordinal
                )
                if (
                    event.freshness != "fresh"
                    or candidate[2] < policy.model_stable_captures
                ):
                    event.notification.available = False
                    event.notification.preview = True
                    event.notification.reason = (
                        "Changed prediction topology; awaiting stable captures"
                    )
            elif any(previous.get("event_id") == event.event_id for previous in old):
                event.event_id = identity(event.event_id, event.due_at)

    def _remember(self, key, value):
        self.candidates[key] = value
        while len(self.candidates) > 1000:
            self.candidates.pop(next(iter(self.candidates)))

    def select(self, connection, event, *, as_of, policy):
        row = connection.execute(
            "SELECT o.event_json FROM event_heads h JOIN event_occurrences o USING (occurrence_id) WHERE h.event_id=? AND h.retired=0",
            (event.event_id,),
        ).fetchone()
        if not row or event.due_at is None:
            return
        accepted = json.loads(row[0])
        anchor = utc_timestamp(accepted["due_at"]) if accepted.get("due_at") else None
        tier_row = connection.execute(
            "SELECT max(t.severity_generation) FROM event_heads h JOIN event_tiers t USING (occurrence_id) WHERE h.event_id=?",
            (event.event_id,),
        ).fetchone()
        accepted_tier = (
            tier_row[0]
            if tier_row and tier_row[0] is not None
            else accepted["notification"]["severity_generation"]
        )
        proposed_tier = event.notification.severity_generation
        moved = (
            anchor is not None
            and abs((event.due_at - anchor).total_seconds())
            >= policy.model_shift_seconds
        )
        escalated = proposed_tier > accepted_tier
        event.schedule_key = accepted["schedule_key"]
        if not moved and not escalated:
            self.candidates.pop(event.event_id, None)
            return
        if event.freshness != "fresh":
            return
        candidate = self.candidates.get(event.event_id)
        target = (
            event.due_at if moved else anchor,
            proposed_tier if escalated else accepted_tier,
        )
        if candidate is None or candidate[0] != target or as_of < candidate[1]:
            self._remember(event.event_id, (target, as_of, 1))
            event.notification.severity_generation = min(proposed_tier, accepted_tier)
            return
        count = candidate[2]
        if (
            as_of - candidate[1]
        ).total_seconds() >= policy.model_capture_spacing_seconds:
            count += 1
            self._remember(event.event_id, (target, as_of, count))
        required = max(
            policy.model_stable_captures if moved else 2,
            policy.model_escalation_captures if escalated else 2,
        )
        if count < required:
            event.notification.severity_generation = min(proposed_tier, accepted_tier)
            return
        # Moving a threshold already behind us cannot repeatedly re-arm it.
        if moved and anchor > as_of and event.due_at > as_of:
            event.schedule_key = identity(accepted["schedule_key"], event.due_at)
        self.candidates.pop(event.event_id, None)
        if len(self.candidates) > 1000:
            self.candidates.pop(next(iter(self.candidates)))
