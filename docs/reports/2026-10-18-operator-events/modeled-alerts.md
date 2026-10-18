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

Candidate `45c4a93bf55fc18eb8465504faa70a5e39b35d96` passed desktop/mobile
foreground sound, two-client acknowledgment, route/position updates, stale and
unavailable sources, explicit deactivation and restart; Overview compatibility,
acknowledgment crash/backup recovery, storage failures and existing #349 exports
also passed. Its complete task-owned runtime was removed. This intermediate run
preceded the final review fixes; final candidate evidence is recorded below when
qualification completes.

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
