# Acceptance Platform Operations

## Purpose and authority boundary

The acceptance platform is a shared operational capability. It owns platform
provisioning, candidate identity validation, isolated runtime resources, evidence
sealing, and cleanup. A product contract supplies only product semantics:
services, static checks, public controls, deterministic assets, and a visible
journey adapter.

An administrator provisions the browser bundle before a branch run. The
administrator creates an immutable bundle record with its absolute executable
path, executable version, revision, byte size, checksum, bundle identifier,
creation time, platform-owned browser-store path, and package/runtime provenance
where applicable. The platform record and executable identity are verified before
launch.

A branch run consumes that verified record; it does not install, replace, or
otherwise provision the bundle. Branch acceptance must not execute `npm`, `npx`,
a Playwright installer, or an installer resolved through inherited `PATH`.
The checked-in default profile is a deliberately unprovisioned template, so it
correctly returns `environment_blocked` until an administrator supplies a
coherent bundle.

## Health certification and fingerprint

Run the `health` lane before any product lane. Health certification verifies the
profile and bundle identity, performs the neutral display/card check, retains its
bounded artifacts, and seals a health fingerprint. The fingerprint binds the
profile checksum, health-card checksum, bundle identity, Docker identity, Compose
identity, measured viewport metrics, capture timestamp, retained-artifact
checksums, outcome, and cleanup status.

Before a product lane begins, it validates the current matching health
fingerprint. Validation re-verifies the health card and evidence manifest before
the product lane starts. A missing, stale, malformed, or unsealed fingerprint is
`environment_blocked`; static checks, runtime controls, and the product journey
must not start. Inspect the sealed fingerprint and its manifest from the durable
evidence root before treating platform health as current.

## Lanes and outcomes

The runner has four lanes:

- `health` certifies the shared platform capability and can claim platform health
  only.
- `static` runs contract-declared product checks after health validation and is
  non-final.
- `diagnostic` collects a bounded, lower-cost product diagnostic and can claim
  only `diagnostic_only`.
- `final` executes the complete final acceptance state machine and can claim
  final acceptance only when every final predicate passes.

Every lane records one outcome: `passed`, `failed`, `environment_blocked`,
`coverage_gap`, or `diagnostic_only`. A final claim is valid only for a passed
`final` lane whose cleanup and evidence finalization also passed. A static or
diagnostic success is not final acceptance.

## One-build final state machine

The final lane uses the validated candidate SHA, profile checksum, and product
contract checksum as one build-ledger key. Its state machine is:

1. Validate the health fingerprint and product contract.
2. Run the declared static checks.
3. Prepare task-owned topology and arm cleanup.
4. Resolve the scoped topology and perform one fresh-image build for the ledger
   key. The platform owns a fixed 1200-second deadline for `docker compose build
   --no-cache --progress=plain`; it is deliberately below the 1800-second external
   final monitor. Every final-critical Compose operation passes combined output through
   bounded, credential-redacted platform retention. Authorization header values,
   including `Bearer` and `Basic` forms, are redacted in full; the retained
   diagnostic, including its truncation marker, never exceeds its byte budget.
   The sealed evidence includes `compose.output.log` on build success, failure,
   and deadline exhaustion. A build timeout or reconciliation/inspection error
   closes its ledger claim as unusable and records the retained BuildKit
   diagnostic as the primary build failure.
5. Reconcile build output and inspected image identities into a usable ledger
   record.
6. Start the scoped services from that record without another build. The platform
   owns a fixed 120-second deadline for `docker compose up -d --no-build --wait`;
   on deadline exhaustion it retains Compose output and classifies startup as
   failed rather than waiting for external transport termination.
7. Exercise public controls and the product's visible journey.
8. Stage evidence privately and validate its bounded inventory.
9. Clean task-owned resources and verify cleanup before computing the final
   claim.
10. Re-verify staged evidence and checksums after cleanup.
11. Seal and atomically publish final authority only if every final predicate,
    including cleanup and post-cleanup verification, holds.

A cached diagnostic can help classify a problem, but cached diagnostics cannot
replace final fresh-image evidence. A new candidate SHA, profile checksum, or
contract checksum requires a new final build-ledger record.

## Final browser execution and interruption recovery

Use this operator sequence for final acceptance:

1. Run `health` and checksum-verify its sealed fingerprint and evidence manifest.
2. Run `static` only after that health validation succeeds.
3. Issue `final` through one tracked runner process with a 1800-second monitored
   budget and durable stdout and stderr capture.
4. The runner, not a caller, owns the headed Xvfb and loopback CDP browser
   resources, its task-owned profile, and pre-journey native display/card metrics.
   Callers must not hand-launch a headless browser as final acceptance evidence.
5. On failure, inspect the runner's sealed diagnostic logs at
   `adapter.stdout.log` and `adapter.stderr.log` in the final evidence root.
6. After an interruption, inspect the final build ledger, inspected image
   identities, and task-owned resources. The runner classifies `SIGINT` and
   `SIGTERM` as final-run failures, retains browser/Xvfb and Compose diagnostics,
   and drains its composite cleanup before it records evidence. Do not retry
   merely because a process stopped: obtain explicit authorization from a human
   operator before one recovery attempt.
7. Verify runner cleanup after the attempt without deleting volumes. Persistent
   volumes are retained unless their removal was explicitly requested.

The tracked runner is the only final-browser operational authority. A caller's
ad hoc browser output, including a manually launched headless browser, is not
final evidence and must not be substituted for the runner's sealed result.

## Evidence and publication

Evidence belongs outside tracked repository content under a durable,
SHA-qualified root. Directories in that root are mode `0700`; retained files are
mode `0600`. The runner writes only bounded, allowlisted artifacts and a manifest
that identifies the candidate SHA and ref, lane, profile and contract checksums,
health fingerprint, browser identity, journey-adapter checksum, capture start and
end timestamps, controls, journey observations, image identity, primary result,
cleanup result, and the maximum evidence claim. The inventory records a byte size
and SHA-256 checksum for every retained artifact.

Final evidence is staged privately before cleanup, then re-verified and sealed
only after cleanup succeeds. The runner atomically publishes final authority only
after that seal and publication verification. A discoverable final authority
exists only after this sequence. If cleanup, sealing, verification, publication,
or later revocation fails, the runner records a non-final result and must not
leave a discoverable final-pass authority.

## Cleanup ownership

One runner-owned cleanup path is armed as soon as task-owned resources exist. On
success, failure, or interruption it drains Compose resources, browser/Xvfb
processes and listeners, the task browser profile, and the generated task root
before it records the result. It retains collected diagnostics before removing
the task root and preserves persistent volumes unless their removal was
explicitly requested.

Cleanup runs on success, failure, and platform blocking after resources were
created. The runner retains the primary failure, records any cleanup failure
separately, verifies that owned resources are gone, and re-verifies evidence
checksums after cleanup. A cleanup failure downgrades a would-be final result to
`failed`; it does not overwrite the primary diagnostic.

## Product contract references

The platform owns operational authority; each product contract owns only its
product semantics. The V2 product contract is
[V2 Mission Retirement Acceptance Contract](../missions/v2-mission-retirement-acceptance.md).
