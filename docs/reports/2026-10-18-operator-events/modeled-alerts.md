# Current modeled restriction alerts: PR #379 follow-up

Product review 6248772010 required significant modeled restrictions to notify an
operator with the page open under normal current inputs. The initial delivery's
withholding of ordinary modeled cues was a functional gap.

## Production behavior

The normal application factory now installs `ProductionEventSources`. It reuses
immutable mission-input capture and `prepare_mission_timeline`, including the
existing transport capability and #348 continuity calculations. It does not save
plans, publish map POIs, change exports or introduce another predictor.

A fresh significant X/Starshield/Ka restriction is eligible five minutes before
its modeled start and while actionable. Existing default sound/vibration output
applies after the browser gesture; ordinary PoP transitions remain visual-only.
Acknowledgment is optional, shared, and affects only repeated notifications.

Mission transport restrictions retain the existing model's mission UTC timing.
The shared #348 service supplies live route-aware PoP ETAs and observed
advisories as a separately timed source in the same chronological feed. Position
refreshes therefore update live estimates without manufacturing a new durable
mission restriction or rearming its acknowledgment at every sample.

Supported route, configuration, catalog, leg and lifecycle publishers share the
repository admission gate. Detached model preparation is revalidated before
publication. Feed reconciliation and acknowledgment validate captured revisions
while holding repository admission through SQLite commit. A changed source is
rejected; an unavailable source preserves last-known information.

Missing optional transport evidence is reported independently. Missing PoP or
missing/malformed Ka data does not suppress a known current X restriction.
Unknown PoP location never means a Starshield service outage. Formerly active
legs retire their old heads on deactivation, removal or switching, including
recovery after restart; never-published inactive legs retain saved planning
rows.

## Qualification

The raw-input-only Docker/Nginx scenario does not replace the production
adapter, inject prediction results or manually designate a source guardable. It
supplies route points/timing, telemetry, coverage and satellite/PoP catalogs to
the real application and records actual browser audio oscillator attempts.

Final production candidate: `3e216a26d0607fa9f6892baa0f8eef5019eceedd`.

All three browser scenarios passed: Overview/display compatibility, actual
nonsecure aircraft-LAN HTTP without secure-context UUID support, and modeled
foreground alerts. The model scenario asserts that the significant X restriction
is still in the future and within five minutes when it becomes eligible, then
records one actual audio oscillator attempt per client after the enable gesture.
Desktop/mobile captures are 1920×1080, 390×844 and 844×390; settled drawer
bounds and horizontal overflow are checked.

- [Exact image/archive identity, checks and cleanup](model-alerts/summary.json)
- [Operational browser assertions](model-alerts/model-alerts-proof.json)
- [All qualification results](model-alerts/qualification.json)
- [LAN HTTP evidence](model-alerts/events-lan-http.json)
- [Acknowledgment crash/backup recovery](model-alerts/events-backend.json)
- [Desktop capture](model-alerts/model-alerts-1920x1080.png),
  [mobile capture](model-alerts/model-alerts-390x844.png),
  [landscape capture](model-alerts/model-alerts-844x390.png)
- [Selected evidence hashes](model-alerts/hashes.json)

The final seed contains no injected model timelines. Earlier intermediate runs
retained legacy example planning rows and exposed ambiguous selectors, audio
readiness timing and premature animation captures; those are superseded by the
raw-only, approaching-warning run above. No prediction result was altered to
make a test pass. All task containers, networks, volumes, processes, listeners,
images and temporary build trees were removed after each run.

Full verification: backend **4,125 passed, 20 skipped**; frontend **1,829
passed**; production build and canonical static gate passed; **31
acceptance/ownership harness tests passed**. The final evidence commit changes
documentation only;
[PR-head CI](https://github.com/bcl1713/starlink-dashboard/pull/379/checks)
verifies the submitted branch after that commit.

Fresh review identified two important defects: per-leg retirement during a
switch, and malformed optional Ka coverage suppressing independent X warnings.
Both have focused regressions observed failing before correction. No critical or
minor findings were reported. The complete backend suite also exposed status
latency while admission was held; status assembly now runs off the event loop
and uses the actual coordinator configuration for the fallback service.

The later LAN-inclusive run exposed an early audio-enable gesture before the
first feed snapshot initialized its output. A focused regression reproduced the
race. The enable button now waits for output readiness, and all 1,829 frontend
tests pass after correction.

## Decisions and limits

- Retain existing source time bases rather than introduce transport ETA
  modeling. Cost if wrong: mission restriction timing can differ from actual
  arrival; the existing live PoP ETA remains visible for the operator's
  judgment.
- Isolate unavailable optional prerequisites rather than require perfect model
  completeness. Cost if wrong: an imperfect but useful warning can still occur,
  consistent with the decision-support requirement.
- Materialize the shared local #348 status producer under admission when needed
  for a current capture; never advance telemetry or replay. Cost if wrong:
  additional feed reads can update advisory reconciliation state. This uses the
  same producer as status and adds no external lookup or predictor.

Local sound/vibration remain browser/device best-effort. No suspended/closed
browser delivery, routing execution, external services or aircraft readiness is
claimed. PR #379 remains draft pending product review; no merge is authorized.
