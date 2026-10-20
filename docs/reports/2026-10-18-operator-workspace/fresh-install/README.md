# Fresh-install production browser checkpoint

Candidate `b4af3e4f9affa430a30985425c35b1fb8381f710`; real backend and Nginx
frontend, private disposable simulation volumes. No Operator database or record
seed, no fixture clock or lifecycle patch. Production main startup and source
factories are used.

The browser created a new mission, observed first-use 503 with no store ID,
explicitly initialized the simulation journal through the shipped UI, and saved
a call, conference, issue and note. Restart retained the same store ID, epoch
and four record IDs. The browser then uploaded a synthetic route and started the
normal mission replay, observed its separate uninitialized run namespace,
initialized it and created the same four record types. All eight receipts are
preserved. Setup/recovery Help was served by the production frontend.

This proves clean-install setup and CRUD in both an explicitly configured
nonproduction simulation namespace and a real newly started replay namespace. It
does not claim exact-frame replay restoration, cross-run journal merging, full
workspace parity or guided training completion. Live and simulation separation,
recovery-artifact refusal and namespace return/restart identities are
additionally covered by backend tests.

The inherited generic `fixture` line in this first summary says fixed scenario
time; that line is a reporting-template defect. This run used the normal system
clock, as its receipts show. The harness metadata is being corrected; no
fixed-clock claim is made for this run.

Cleanup in the summary confirms no task containers, networks, volumes, listeners
or child processes remained.
