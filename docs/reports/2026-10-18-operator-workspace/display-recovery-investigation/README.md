# Connected display recovery investigation

Candidate `7bece5bf28f3a210ed900f0df7e402939b29f78f`: failed final native
display gate. The inspected foreground window was visible before/after the
failure. Backend visibility settings were correct; the native wind object
remained absent at the180-second scene deadline. This disproves the earlier
background-tab explanation as a complete cause.

Retained browser trace (local task evidence root
`test-results/gfs-foundation/1792388342763786329/7bece5bf28f3a210ed900f0df7e402939b29f78f`)
shows revision5 wind unavailable at192/242seconds, ready at302seconds, then one
grid.json404 for the main display. At364seconds its next poll obtained the
descriptor and all four components; the last completed near373seconds, at the
scene deadline. The other display obtained all buffers near313seconds. Backend
admission deliberately rechecks current settings/clock/worker and can reject a
URL after a catalog read; its second-stage control lock is nonblocking. The
trace does not prove which admission guard rejected this specific response.

Focused tests reproduced the frontend recovery gap: one temporary grid
descriptor/component404 failed the load and deferred recovery to the
next60-second catalog poll. Three new cases now verify one retry after250ms,
repeated rejection bounded to two requests, cancellation during backoff,
unchanged original load ownership/deadline and released timers/resource
reservations. Existing validation remains mandatory. No server admission guard
or scene assertion is relaxed. Native rerun remains required before calling this
fixed.

All resource inventories are empty; independent host PID/start-time verification
found no surviving owned processes and ports56540/56541 are free.
