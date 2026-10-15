# Manual-testing feedback continuation

## Task 9: Apply manual-testing feedback

**Authority:** Owner feedback during manual testing, 2026-10-15, supersedes the
intermediate revision-review requirement in the approved design.

**Interfaces:** Keep ordinary mission identity, history, active-leg protection and
source ownership. Apply incoming conflicting source fields automatically; keep
compatible manual edits. Order shared mission views and exports by effective
departure time. Preserve the user's isolated preview data during its update.

1. Reproduce automatic-acceptance and chronological-order failures with tests.
2. Remove the JSON review UI, automatically apply revisions and retain retry and
   concurrency guards. Handle older ready operations without manual approval.
3. Verify source/KML departure order and takeoff overrides through shared storage.
4. Update production acceptance to require automatic revision and chronological
   API order; run full backend, frontend and static gates plus exact-head
   production CSV/PDF/clone qualification.
5. Update the user-requested preview, preserving volumes, and leave it running
   with its ownership and stop command. Push and update the PR against dev.
