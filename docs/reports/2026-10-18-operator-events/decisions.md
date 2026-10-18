# Execution rulings

These decisions preserve the approved scope and are recorded in execution order.

1. New-store schema assertions advance from 1 to 2; original migration 001 keeps
   its checksum. Wrong backup version metadata could prevent restore.
2. Ordinary model publishers lack a complete shared invalidation guard, so
   capture stays read-only and modeled acknowledgment fails closed. The cost is
   unavailable modeled acknowledgment until a participating adapter is proven.
3. Spaced model stability uses optional bounded runtime candidates; accepted
   anchors/tiers remain durable. A backend restart delays pending candidates.
4. HTTP-safe cue coordination uses IndexedDB reservations/leases, additionally
   Web Locks when available. Denied IndexedDB disables automatic local cues; the
   timeline and backend acknowledgment remain available.
5. Legacy Next requirement remains only as a visibly timestamped fallback when
   live feed retrieval fails. That fallback requires manual refresh; broader
   layout consolidation stays in #376.
6. Acceptance uses `starlink-operator-events-368`, matching the existing
   ownership admission contract. This corrects the planned project prefix with
   no product cost.
7. Ambiguous topology previews stay transient and retain prior rows as unknown
   until stable replacement. This can delay automatic notification of changing
   predictions; the uncertainty remains visible.
8. Matching mission/leg IDs alone cannot establish model-input alignment.
   Unproven sources remain advisory with automatic modeled restriction cues
   withheld. Ordinary sources need proven revision alignment to enable them.
9. Synthetic HTTP clock/source controls use an explicit acceptance-only flag.
   Real isolated route-registration tests replace a source-text prohibition. The
   control API exists only in the selected test fixture, never production
   `main`.

The fresh reviewer accepted these rulings. Its four Important findings were
fixed rather than waived; see [review outcomes](review.md). No Minor findings or
unjudged behaviors were deferred.
