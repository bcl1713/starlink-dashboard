# Lean execution revision and existing capability map

This revision applies the
[user's deployment and reuse clarification](https://github.com/bcl1713/starlink-dashboard/pull/382#issuecomment-6253613063)
after
[plan approval](https://github.com/bcl1713/starlink-dashboard/pull/382#issuecomment-6253561956).
The user has three computers and one aircraft production machine. Training runs
as an explicit separate instance/data directory on a nonproduction computer. The
complete mission cockpit, full walkthrough, guide and quick reference remain
required. This changes training implementation, not feature scope or
correctness.

## Necessary work versus infrastructure removed

| Keep                                                                               | Reuse rather than rebuild                                                                                                                   | Remove from the critical path                                                                                                 |
| ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Persistent unsent drafts, frozen retries, immutable history and correct identities | Lift/adapt `useOperatorJournal` and existing durable draft hooks; keep existing command/API authority                                       | A second implementation of the lifecycle/write engine                                                                         |
| Clear complete workspace and discoverable call/conference commands                 | Existing typed editors, lists, lifecycle builders and record services                                                                       | Replacing working forms with a new generic CRUD framework                                                                     |
| Hands-on whole-system training                                                     | Existing synthetic seed/raw-input/clock/relay/ownership and archive fixture patterns under `tools/acceptance/operator-journal/`             | New `app/training` package, production training orchestration APIs, server-side progress service and general session registry |
| Repeatable reset and restart/resume                                                | One private data root, existing seed manifest and raw checkpoint files, versioned browser guide progress; launcher stop/reset/start         | Hot-swapping live stores or general transactional reset API                                                                   |
| Multi-leg journal continuity and truthful simulated time                           | A small tooling-only fixture binding using existing `ScenarioClock`/`EventsClock`, stable simulation ID and existing runtime injection seam | New production namespace semantics, new clock class or replay snapshot/reconstruction engine                                  |
| Real predictors, flight events and archives                                        | Existing raw simulation input helpers, normal flight-status/replay services and production PoP/ETA/export implementations                   | Canned predicted outcomes, a second predictor or fixture answers standing in for flight lifecycle                             |
| Import boundary practice                                                           | Temporary clean app instance only for T10, using the same images and existing archive-destination pattern                                   | Permanently running a second training stack                                                                                   |

## Concrete reuse evidence and limits

`tools/acceptance/operator-journal/backend_fixture.py` already rejects
non-synthetic configuration and non-simulation mode, explicitly seeds owned
data, injects an existing scenario clock into `OperatorRuntimeBinding`, and
exposes fixture-only `POST /api/_synthetic/operator-model-inputs`. Normal
`main.py` factories remain intact. `seed.py::seed_demo` persists an idempotent
seed manifest and initializes an explicit simulation store.
`model_inputs_fixture.py` persists raw inputs and feeds the real production
model adapter; it also directly restores flight phase and seeds records, which
must NOT be mistaken for learner work or proof of the normal flight lifecycle.

Training reuses those helpers selectively. Add a prerequisite-only seed option
and a raw-input helper that does not install completed learner records or
restore flight phase. Preserve existing acceptance defaults/tests. The thin
training entrypoint lives in tooling, not `app/`; it supplies the existing
binding's context/clock seam and consistent model/PoP context within that
process only. It uses one explicit simulation namespace per owned data root.
Normal deployed live/simulation namespace behavior is unchanged. Test actual
replay activation and leg changes against that fixture before building the guide
around it.

The existing fixture route is not a production API. Training-only import of this
entrypoint, a simulation-mode check and a private root marker suffice; there is
no need to add instance UUID headers to every application request. No aircraft
mounts, real dish discovery or live mode are used. Bind to loopback by default;
preserve the actor's Docker daemon/context. Setup documents the explicit
nonproduction-computer assumption rather than attempting to police all machines.

Reset mission stops only the owned training project, retains its old root and
starts a fresh sibling root/seed. The guide's Reset mission action displays the
exact local launcher command; it does not claim a hot reset occurred. Reset
guide only resets browser progress and is labeled separately.
Next/back/skip/resume are in-product guidance; Back never undoes a record and
Skip never marks it passed. This deliberately trades automatic hot reset for a
small documented local command.

Browser progress is keyed by fixture version, training origin, store identity
and mission. It is revalidated from current records/events/export state on
resume; its completion flags are not evidence. Restart uses persisted fixture
inputs and journal without replaying learner writes. An ephemeral paced run may
require restarting the flight segment through existing preview/activation; state
this explicitly and do not promise an exact restored replay frame. Raw-input
checkpoint lessons can resume their persisted inputs. No new replay persistence
engine.

## Existing API and control mapping for T01–T11

All Operator writes retain `Idempotency-Key`, `X-Operator-Store-Epoch` and
expected versions. The learner uses the real UI/controller; the guide evaluates
its reads and receipts rather than auto-performing the learner's actions.

| Stage                     | Existing capabilities used                                                                                                                                                                                                                           | Small addition / honest limitation                                                                                                                                                                                                                                                                                                              |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| T01 Context               | `GET /api/v2/missions`, `/{mission_id}`; `GET /api/v2/operator/health`, `/records`; `GET /api/flight-status`; existing mission/scope types                                                                                                           | Guide targets and readable workspace selectors; no training context API                                                                                                                                                                                                                                                                         |
| T02 Calls                 | `POST /api/v2/operator/records`, `PUT /records/{id}`, `/remove`, `/restore`; `CallEditor`, `callDraft`, `callTiming`                                                                                                                                 | Adapt layout/draft ownership; prep/unknown/status semantics stay intact                                                                                                                                                                                                                                                                         |
| T03 Conferences/customers | Same record API; `conferenceCommands.ts::{conferenceCommand,joinCommand,leaveCommand,resumeCommand}`                                                                                                                                                 | Visible Create/Establish/Verify/Reuse/Close and independent participation actions; no bridge provisioning                                                                                                                                                                                                                                       |
| T04 Display/alerts        | `overviewPresetsApi`, existing Overview settings services/window protocol, `useEventAlerts`; `GET /api/v2/operator/events`, `POST /events/acknowledge`                                                                                               | Open a training Overview window; guide reads actual receipts/capabilities; no simulated successful recenter                                                                                                                                                                                                                                     |
| T05 Flight/predictions    | `POST /api/v2/missions/{m}/legs/{l}/simulation/preview`, `/activate`; `GET /api/simulation/run`, `/run/{id}/route`; normal `POST /api/flight-status/depart`, `/arrive`, `/transition`; real `production_live_timing.py` / `production_pop_events.py` | Existing fixture raw-input seam advances known synthetic position/speed/freshness; normal lifecycle APIs/replay generate flight state and archival. Never treat fixture phase overwrite as lifecycle evidence. Manual phase endpoints are unavailable while an active replay disallows plan edits; lessons choose one supported path at a time. |
| T06 Transport             | Existing typed record API; `TransportEditor`, `TransportServiceRow`, `transportForms`, event `transport_review`                                                                                                                                      | Contextual applied-only default, multi-service/stage/precision/check preservation; no new decision engine                                                                                                                                                                                                                                       |
| T07 Issues/capability     | Existing typed record API; `OperatorIssues`, `CapabilityAssessments`, `IssueActivity`, `IssueCorrection`                                                                                                                                             | Guide references operational update versus historical correction; existing backend rules stay authoritative                                                                                                                                                                                                                                     |
| T08 Notes/recovery        | Existing record/history API, `JournalEditor`, `JournalHistory`, existing exact retry/reconcile; maintenance CLI `backup/check/restore` on the private training root                                                                                  | Reuse acceptance transport-failure relay/interception patterns for lost receipt; counterpart browser makes a real 409. Browser offline exercise or documented DevTools/runner network loss; no production fault API or fake accepted write.                                                                                                     |
| T09 Ground gap/leg 2      | Existing flight lifecycle and `POST /api/v2/missions/{m}/legs/deactivate`, leg `/activate`; record `between_legs` associations; existing flight-event capture                                                                                        | Thin fixture namespace binding keeps prior training records visible; test it early. Keep the actual replay ID separate from the stable fixture journal namespace.                                                                                                                                                                               |
| T10 Postflight/ZIP        | `POST /api/v2/missions/{m}/export` and `/export-preparations`; GET status/download, DELETE preparation; `POST /api/v2/missions/import`; existing `ExportDialog`/`ImportDialog`                                                                       | Temporary clean destination with Operator sentinels; actual ZIP/PDF/telemetry/journal/checksum validation. Human extraction step is explicitly human-observed, never inferred from a Next click.                                                                                                                                                |
| T11 Other parity branches | Existing record fields/history, event occurrence eligibility, display groups/presets/history/boundaries, provider/storage failures and maintenance contracts                                                                                         | Each parity entry links to real control/evidence; optional branches remain required coverage, not dropped features                                                                                                                                                                                                                              |

## Milestones and revised estimate

| Milestone | Work                                                                                         | Engineer-days | Deliverable                                                                                  |
| --------- | -------------------------------------------------------------------------------------------- | ------------- | -------------------------------------------------------------------------------------------- |
| M1        | Baseline plus persistent draft/command ownership adapters                                    | 2–3           | Verified state checkpoint; working lifecycle engines retained                                |
| M2        | Approved shell and complete working views, reuse editors/lists/actions                       | 3–5           | Fast usable full-parity candidate workspace in 5–8 cumulative days; private until acceptance |
| M3        | One-instance fixture launcher, minimal namespace/time seam, guide progress and whole mission | 2–3           | Real hands-on T01–T11; temporary import target only for T10                                  |
| M4        | Full shipped guide, screenshots, quick reference and Help                                    | 2–3           | Procedures linked to real controls and training stages                                       |
| M5        | Production parity, failures, devices, first use, timings and backout                         | 3–6           | Release-ready evidence after correction of failures                                          |

Revised planning range: **12–20 engineer-days**, excluding review, first-time
user and device availability. It is based on direct reuse, not simply
compressing the previous estimate. It is not a deadline promise. M2 is a usable
candidate/review milestone, not permission to close/release the issue without
M3–M5. The full training/guide/quick-reference deliverables remain in the final
gate.

If the thin fixture seam cannot preserve history/source identity using existing
injection points, report the exact failing test and propose the smallest change
before expanding infrastructure. Do not silently resurrect the removed server
orchestration architecture, rewrite replay or weaken draft/API correctness.
