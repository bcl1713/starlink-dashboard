# Aviation weather native diagnostic — 2026-10-06

The real-source native Overview diagnostic passed at candidate
`76605c913a87819b4113537213928bb8000e32fc`. This is a diagnostic result, not final
product acceptance. Issue #290 remains open. The later persistent-lock shell fix
and this report commit require the controller's separate exact-current-HEAD run.

Private sealed evidence:
`/srv/starlink-acceptance/evidence/issue-290/diagnostic/starlink-290-task5-attempt-7905q8te/76605c913a87819b4113537213928bb8000e32fc`.
All nine success/failure attempt manifests and fingerprints were independently
verified after cleanup; earlier evidence was preserved.

| Native measurement                         | GFS 500 hPa | GOES-19 C13 |
| ------------------------------------------ | ----------: | ----------: |
| Real-source GPU/independent Python samples | 10          | 10          |
| Maximum quantity error, K (limit 0.01 K)   | 0.004220    | 0.003234    |
| Maximum palette error, RGB × 255 (limit 3) | 0.482463    | 0.486923    |

The quantity and mask readback use the same packed Int16/manual-bilinear shader
as the native overlay. Every stencil corner must be valid, including zero-weight
neighbors. Oracle coordinates come from independent CPU intersections with the
actual tessellated mesh at rounded native viewport pixels. The shader reconstructs
its point from the native camera ray and the actual triangle plane. Earlier crop
and inverse-trigonometry hypotheses were ruled out; no tolerance was widened.
Palette checks use an interior pixel, a known linear framebuffer background,
opacity 0.40, and no multisampling, tone mapping, or custom output conversion.

All four report gates passed: real-source provenance, native GPU/mask/palette,
required controls and labels, and owned runtime cleanup. Twelve separately labeled
controls cover seams, poles, invalid masks, failed installation, holes, expiry,
cancellation, wind direction, regional scan intervals, advisory dateline handling,
concurrent replacement ownership, and camera restoration. Thirteen screenshots
retain world/North Atlantic/antimeridian/polar model views, desktop/fullscreen/mobile,
VICTOR6 and route/aircraft/station advisory views, and Americas/Atlantic-limb/night
satellite views, with per-capture camera and viewport receipts. All 250 recorded
browser requests stayed on the permitted local origin.

The browser was Chrome 153.0.8010.12, WebGL2 through ANGLE Vulkan SwiftShader,
using the administrator profile at 1920×1080 and DPR 1. Normal native canvas size
was 1920×1015; fullscreen was 1920×1080; mobile used a 351×360 canvas in a
390×844 viewport. Conservative allocation reservation peaks were 4,696,352 bytes
encoded, 25,666,368 decoded/geometry, and 12,834,880 GPU, below 16/32/16 MiB caps;
all returned to zero. These include replacement and diagnostic color attachments.
Whole-browser process-tree peak summed RSS was 3,320,229,888 bytes (shared pages
can be counted more than once), separate from incremental weather allocations.

Each source regenerated offline from immutable captures in its own 1 CPU/1 GiB
worker, bounded to 120 seconds plus a 10-second termination grace, using the
pinned scientific image and the candidate source mounted read-only. GFS/advisory/
GOES normalization took 0.854/0.084/1.173 seconds and reported peak process RSS
204,963,840/56,758,272/120,573,952 bytes. Source controls and independently sampled
normalized products were retained alongside hashes, URLs, provenance, and times.
GFS is the 00Z F006 500 hPa field valid 06Z, without a flight-level claim. GOES
retains the full 00:00:20.900–00:09:52.800 UTC scan and brightness
temperature in K.
Advisory display explicitly replays descriptor epoch 1791288447898
(2026-10-06T12:07:27.898Z); expired/cancelled controls remain inactive otherwise.

The preceding attempt failed the port-cleanup gate; its exact transient cause was
not established by that receipt. The passing retry retained TCP TIME_WAIT state
06 with inode 0 and no owner on port 15290, then waited 57.13 seconds until the
same exclusive bind criterion passed. No gate was relaxed. Owned browser processes,
contexts, profiles, CDP endpoint, worker groups, Compose containers/networks/volumes,
and ports 15290/18290 were verified absent; no descendant required forced killing.

Verification: 126 named scientific/runner/report/typing tests passed with native
bootstrap and warnings as errors; 62 frontend proof/radar tests passed. Focused
TypeScript, ESLint, formatting, Python/JavaScript/shell syntax checks and the
production image build passed. The subsequent persistent-lock change has its own
RED/GREEN shell-invocation regression and 19 passing runner/report/typing tests.

WIFS access, flight-level interpolation, worldwide feed completeness, and global
satellite seam coverage remain unproven. Brightness temperature is not cloud height.
No continuous ingest, production aviation API, or product implementation dispatch
is introduced. The test-only fixture exposes normalized assets only.
