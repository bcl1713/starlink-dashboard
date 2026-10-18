# Whole-branch review and native fixes

A fresh read-only reviewer examined `30d628c8..5d399811` against the approved
specification, eight-task plan, Review Focus and recorded rulings. It reported
four Important findings, no Critical/Minor findings and no declined judgments.
All four entered one native fix pass; no second review was dispatched.

1. **Ordinary aircraft HTTP lacked secure-context UUID support.** The emitter
   and acknowledgment controller now use the existing HTTP-safe client-ID
   helper. Both new tests failed with `crypto.randomUUID` absent before the fix,
   then passed. Production acceptance additionally checks an actual non-loopback
   HTTP origin with Chromium host mapping, without mocking application/API
   responses.
2. **Ambiguous topology counted unstable/stale captures.** Stale captures now
   reset the candidate; fresh captures must remain within the configurable
   material-shift threshold. The stale-then-fresh and material-shift regression
   failed before the fix, then passed. Preview candidates remain transient.
3. **Restriction families lacked actual captured route geometry.** Existing PoP
   publication metadata now carries a geometry-only fingerprint; the source
   adapter carries it into restriction identity. Saved plans use their route ID
   and captured sample geometry. Timing/position forecast revisions do not alter
   route geometry. A real-source test proved identical refresh identity and a
   new occurrence after replacing geometry while retaining overlapping bounds.
4. **Finished model windows remained in Attention indefinitely.** Fresh aligned
   evidence now retires ended restriction/PoP windows into bounded recent
   history. Unavailable/stale/unaligned evidence retains unknown last-known
   rows. The projection regression failed before the fix, then passed; a feed
   test also verifies disappearance from default feed and expiry from history
   after 24h.

Focused backend: 32 passed, plus the history-feed test. Full frontend: 1,828
passed; lint/build passed under Node 22.22.2. Harness: 26 passed. Replacement
production acceptance passed all three browser scenarios, durability, physical
storage failures and actual #348/#349 integrations on candidate
`7d0c61fde80a1dd541474d54a812ac4e98a932c8`, with complete cleanup. Full backend
rerun and final-head CI remain mandatory handoff checks tracked in PR #379.
