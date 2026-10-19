# Connected display and persisted restart acceptance

Exact runtime and browser source: `bd8069fb0c75558d6b58fc46639ae02bdca5aebc`.
Both native production-browser cases passed: the complete connected
display/preset/conflict/unavailable/replay sequence (10.6minutes), then actual
ordinary backend and scientific-worker restart on the same persistent volumes
and fresh connected Overview windows (1.0minute).

After restart, radar/aviation settings and saved preset bodies exactly equal
their original pre-restart values. Both Overview contexts admit native wind and
SIGMET plus radar and retain the five chosen replay network cards with
unavailable measurements. Observed post-restart native waits were7.6seconds
and39.4seconds. The unchanged native scene budget is180seconds. Sources are
explicitly synthetic operational-format inputs; decoder, worker, IPC, API and
native scene are real. Software SwiftShader does not establish physical-device
GPU performance.

This proves persisted settings and fresh-window rendering after service restart.
It does not claim uninterrupted recovery of already open tabs through a restart.
Keyboard/physical-device use and uncoached human interpretation remain separate.

The second browser invocation uses a distinct output directory, preserving any
first-invocation artifacts. Both reports and all image/source identities are
retained. Cleanup inventories are empty; relay stopped; independent host
PID/start-time verification found no survivor and ports56540/56541 free.
