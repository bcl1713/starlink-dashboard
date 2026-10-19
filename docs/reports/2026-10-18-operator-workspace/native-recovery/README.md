# Native recovery and epoch quarantine

Candidate `dc44e086bded909a224cbcff9d365f07c11fe8c2`, private r35 recovery-only production browser exercise: one case passed in 19.6 seconds. It creates a note through the real UI, uses the existing native backup CLI, then commits a second real UI note and drops its response to create an actual uncertain request.

The private wrapper stops only its backend writer, performs the existing offline restore, restarts and runs native integrity checking. Ordinary API snapshots, the original validated backup/checksum and native restore-report/preserved identity agree. The first note survives, the post-backup note is absent, the store ID remains stable and its API epoch changes. The reloaded browser retains exactly the original request body/key/old epoch; it is quarantined with retry disabled. Only one POST was made.

At desktop, portrait and landscape, the guide loads the native report and revalidates current complete history plus the actual quarantined request. T08 backup and T11 epoch outcomes are explicitly labeled tooling evidence. Guide navigation/observations remain scoped to the restored epoch. T11 remains Incomplete; the test supplies no human observation. Raw reports, requests, receipts and screenshots are retained here.

All task Docker containers, networks and disposable volumes are gone. Host cleanup verified 55 command groups, no surviving owned processes/relays and free private ports 56533/56534. The trace remains under `/tmp/issue-376-training-proof-20261019-r35/browser/recovery/`.

This targeted result does not replace the earlier full linked course/archive result or establish the final provider/parity, display, performance, accessibility or uncoached human gates.
