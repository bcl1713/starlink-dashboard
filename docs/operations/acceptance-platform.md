# Acceptance Platform Operations

## Purpose and authority boundary

The acceptance platform is a shared operational capability. It owns platform
provisioning, candidate identity validation, isolated runtime resources, evidence
sealing, and cleanup. A product contract supplies only product semantics:
services, static checks, public controls, deterministic assets, and a visible
journey adapter.

An administrator provisions the browser bundle before a branch run. The
administrator records the bundle executable, version, byte size, and checksum in
a platform profile. A branch run consumes that profile; it does not install,
replace, or otherwise provision the bundle. The checked-in default profile is a
deliberately unprovisioned template, so it correctly returns
`environment_blocked` until an administrator supplies a coherent bundle.

## Health certification and fingerprint

Run the `health` lane before any product lane. Health certification verifies the
profile and bundle identity, performs the neutral display/card check, retains its
bounded artifacts, and seals a health fingerprint. The fingerprint binds the
profile checksum, health-card checksum, bundle identity, measured viewport
metrics, retained-artifact checksums, outcome, and cleanup status.

Before a product lane begins, it validates the current matching health
fingerprint. A missing, stale, malformed, or unsealed fingerprint is
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
   key.
5. Reconcile build output and inspected image identities into a usable ledger
   record.
6. Start the scoped services from that record without another build.
7. Exercise public controls and the product's visible journey.
8. Stage, validate, checksum, verify, and publish evidence only if all final
   predicates hold.
9. Clean task-owned resources and verify cleanup before computing the final
   claim.

A cached diagnostic can help classify a problem, but cached diagnostics cannot
replace final fresh-image evidence. A new candidate SHA, profile checksum, or
contract checksum requires a new final build-ledger record.

## Evidence and publication

Evidence belongs outside tracked repository content under a durable,
SHA-qualified root. The runner writes only bounded, allowlisted artifacts and a
manifest that identifies the candidate SHA and ref, lane, profile and contract
checksums, health fingerprint, controls, journey observations, image identity,
primary result, cleanup result, and the maximum evidence claim. The inventory
records a byte size and SHA-256 checksum for every retained artifact.

Final evidence is staged privately, sealed, checksum-verified, and then
published atomically. A discoverable final authority exists only after
publication verification. If sealing, verification, publication, or later
revocation fails, the runner records a non-final result and must not leave a
discoverable final-pass authority.

## Cleanup ownership

One runner-owned cleanup path is armed as soon as task-owned resources exist. It
removes only task-owned runtime resources, display/profile resources, temporary
files, and generated topology. It preserves persistent volumes unless their
removal is explicitly requested.

Cleanup runs on success, failure, and platform blocking after resources were
created. The runner retains the primary failure, records any cleanup failure
separately, verifies that owned resources are gone, and re-verifies evidence
checksums after cleanup. A cleanup failure downgrades a would-be final result to
`failed`; it does not overwrite the primary diagnostic.
