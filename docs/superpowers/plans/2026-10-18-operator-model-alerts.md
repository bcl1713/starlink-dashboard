# Production modeled restriction alerts: review follow-up

Native execution continues on PR #379. Product review 6248772010 requires the
original #368 foreground modeled-alert scope to work with real production inputs.
The earlier fail-closed fallback remains necessary for invalid inputs; it cannot
serve as completion of the normal valid-input path.

## Contract and design

Reuse the existing immutable mission-input capture utilities and
`prepare_mission_timeline`. Capture effective routes, leg configuration, POIs,
transport/catalog/coverage prerequisites and PoP catalog bytes. Prepare detached
inputs without publishing POIs, saving plans, exporting, or adding a predictor.
Cache prepared models by content revision, never by each polling timestamp.
Mission UTC restrictions remain planned/model estimates, not observed outages or
independently verified routing. Existing #348 live observations remain advisories.

The normal Operator router installs a production source adapter from the
application's real route/POI managers, current configuration, telemetry/lifecycle
providers and existing PoP service. It must not depend on a fixture adapter.
Only complete, fresh, namespace-matching current-input captures can publish an
aligned guardable source. Unknown inputs keep last-known rows and explicit reasons.
Ordinary PoP transitions remain visual-only.

All supported in-process route/configuration, telemetry publication and flight/
replay lifecycle mutations participate in the existing repository admission gate.
Existing mission/planning commits already use it. Real source publication uses
repository gate → publication lock → Operator SQLite. A registered validator
recaptures current input identity and checks freshness before acknowledgment
enters SQLite, while the admission gate stays held through commit. Changed
inputs return 409; unavailable evidence returns 503. This is local application
publication consistency, not an atomic claim about external physical observations
or unsupported out-of-band file writes. Catalog/file replacements are recaptured
and checked before local acceptance; no stale cache is relabeled current.

Preparation happens outside admission, using detached captured views. Revalidate
before publishing; discard changed results. Keep bounded caches, no new worker,
service, background delivery promise or export behavior. Reconnection and restart
use existing occurrence/acknowledgment contracts.

## Tasks

1. **Real input contract and admission.** Add current-input capture and validator
   tests for real route/config/catalog/leg/lifecycle replacement, unknown sources,
   source mutation during preparation and during acknowledgment. Verify publisher
   and mutation paths share admission; preserve lock ordering and receipt-first
   retry. Observe failures before implementation.
2. **Production source adapter and wiring.** Build/cache existing mission
   preparation from captured views, publish explicit alignment proof and guard
   validators, and install the adapter through normal app/router factories.
   Test significant restrictions eligible while ordinary PoP windows remain
   advisory, source changes replacing/retiring occurrences, protected activity,
   acknowledgment suppression, multiple clients, restart and backup.
3. **Real-source acceptance.** Extend the test-only raw-input controls to use the
   real production adapter and actual route/timeline/PoP calculation. Do not
   inject prediction outputs or manually label an adapter guardable. Exercise
   foreground grouped cue, gesture-gated output, mobile/desktop, acknowledgment,
   route/position changes, stale/partial reasons, concurrency and restart.
4. **Qualification and review.** Run appropriate backend/frontend/harness checks,
   then full suites. Commit candidate and run exact-SHA production Docker/Nginx
   acceptance with actual #348/#349. Obtain one fresh whole-diff review, fix
   important findings with regressions, requalify changed product code, publish
   evidence, push and verify final-head CI. Keep PR draft; no merge.

Each task uses bounded tests and commits. Record task ownership before runtime
startup and use the existing acceptance Owner for scoped cleanup. Retain the open
PR worktree and selected synthetic evidence; remove task runtime resources.

## Review Focus

- Every supported model-input publisher and invalidation path participates;
  direct/legacy paths must not silently bypass the authority boundary.
- Immutable captures and fingerprints match what preparation actually consumed,
  including alternate routes, POIs, satellite/Ka catalogs and configured PoP bytes.
- New telemetry/prediction revisions do not create notification noise or allow
  obsolete occurrence acknowledgment; admission/SQLite lock order cannot deadlock.
- Missing or partial evidence never creates a false all-clear or modeled outage.
- Integration acceptance uses normal production wiring and real calculations,
  with no precomputed restriction or synthetic alignment-authority injection.
