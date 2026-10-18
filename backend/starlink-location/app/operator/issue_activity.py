"""Pinned issue update lineage; revision JSONL is distinct from operational messages."""

from .projection_models import IssueUpdate, RevisionIdentity


def derive_issue_updates(revisions, *, store_id):
    updates = {}
    roots = {}
    groups = {}
    for record in sorted(revisions, key=lambda r: r.journal_seq):
        if (
            record.record_type != "issue"
            or record.operation not in ("create", "update")
            or not record.payload.update_text.strip()
        ):
            continue
        identity = RevisionIdentity(
            store_id=store_id, record_id=record.record_id, version=record.version
        )
        target = record.payload.corrects_version
        key = (record.record_id, record.version)
        root = roots[(record.record_id, target)] if target is not None else identity
        roots[key] = root
        root_key = (root.record_id, root.version)
        groups.setdefault(root_key, []).append(record.journal_seq)
        effective_at = (
            record.payload.corrected_update_at
            if target is not None
            else record.time.occurred_at
        )
        updates[record.journal_seq] = IssueUpdate(
            kind="correction" if target is not None else "update",
            root_identity=root,
            corrects_identity=(
                RevisionIdentity(
                    store_id=store_id, record_id=record.record_id, version=target
                )
                if target is not None
                else None
            ),
            selected_identity=identity,
            superseded_by=None,
            effective_at=effective_at,
            text=record.payload.update_text,
            is_selected=True,
            entered_later=(
                effective_at < record.recorded_at if effective_at is not None else None
            ),
        )
    for sequences in groups.values():
        selected = updates[sequences[-1]].selected_identity
        for index, seq in enumerate(sequences):
            item = updates[seq]
            item.is_selected = index == len(sequences) - 1
            if index + 1 < len(sequences):
                item.superseded_by = updates[sequences[index + 1]].selected_identity
            item.selected_identity = selected
    return updates
