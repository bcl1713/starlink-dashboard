# Acceptance Evidence Retention Design

## Purpose

Acceptance runs correctly retain sealed evidence after task cleanup. They do not
currently retire superseded candidate evidence, durable logs, ledgers, empty
parent task directories, or local review artifacts. This design prevents those
roots from growing indefinitely without weakening the evidentiary authority of a
final accepted lane.

The policy applies to repository-owned acceptance maintenance. It does not grant
permission to delete user repositories, browser profiles, production stacks,
Docker volumes, unrelated worktrees, or administrator-owned provisioning files.

## Goals

- Preserve the current checksum-verified final-acceptance authority and no more
  than three completed candidate generations per lane.
- Prune completed superseded candidate evidence by generation count, not age.
- Remove completed runner-owned detached checkouts after their lane has sealed
  evidence and cleaned its runtime resources.
- Bound runner-owned Docker images, Buildx builders, workspaces, and GitHub
  Actions build records to the same three completed generations.
- Remove empty task-root parent directories after an ownership and liveness check.
- Make every candidate deletion dry-run-visible, manifest-aware, bounded, and
  auditable.
- Make retention part of the repository-owned final-lane preflight so it runs
  consistently on any approved compute host without a host-owned service.
- Keep documentation, tests, and cleanup reports aligned with the implemented
  contract.

## Non-goals

- Reclaim Docker volumes, browser stores, profiles, user-owned repositories, or
  arbitrary home-directory files.
- Rewrite, repair, or make a corrupt sealed evidence envelope look valid.
- Treat a failed, partial, malformed, or unverified final lane as final authority.
- Retrospectively classify existing Oracle-local directories for deletion.
- Run the retention routine at the end of an acceptance lane.

## Retention classes

The retention command classifies only data below an explicitly supplied,
canonical acceptance state root. It never follows symlinks and refuses a root or
child that resolves outside that root.

### Protected final authority

A candidate is protected when all of the following hold:

1. Its candidate directory contains a readable, regular sealed manifest and
   checksum inventory.
2. The inventory verifies from the candidate directory.
3. The candidate envelope binds the exact SHA, ref, health-fingerprint digest,
   and runner-manifest digest.
4. The runner manifest reports `outcome: passed`, `final_acceptance: true`, and
   `maximum_evidence_claim: final_acceptance`.
5. Its discoverable authority is present, checksum-valid, and not revoked.

The most recently sealed protected candidate always consumes one of the three
retained generation slots. The other two slots go to the newest completed
candidates not selected as protected. Ordering uses the manifest's validated UTC
completion time; ties, unparsable timestamps, or multiple incompatible
authorities fail closed and retain all affected entries. Its associated final
ledger and SHA-qualified final log are also protected.

### Superseded final and failure evidence

A candidate that is not protected is eligible only when it falls outside the
three newest completed candidate generations for its lane, its sealed manifest
is internally valid, and its candidate, authority, and log associations are
unambiguous. This class includes failed final attempts and older valid final
candidates superseded by the protected authority. A malformed, missing, revoked,
or checksum-invalid entry is reported as an anomaly and is retained; the command
must never delete evidence merely because it cannot prove what it is.

### Health, static, and diagnostic evidence

SHA-qualified health, static, and diagnostic roots are eligible when they fall
outside the three newest completed candidate generations for their lane. Each
eligible root must either have a valid manifest whose artifact inventory
verifies, or be an empty task-owned directory. Unknown nonempty content is
retained and reported as an anomaly.

### Logs, ledgers, and task directories

- A log or ledger that unambiguously belongs to the protected final authority is
  retained indefinitely.
- A SHA-qualified final log or ledger belonging to an eligible superseded
  candidate is eligible with that candidate generation.
- Health/static/diagnostic logs are eligible only when their strict filename/path
  association matches an eligible candidate generation.
- The command removes empty task-directory parents only. It does not remove a
  nonempty task root, task workspace, or any Docker volume.
- Before removing empty task parents, it checks for task-owned live Compose
  resources and fails closed if any matching active resource is found.

## Command design

Add a repository-owned maintenance command, exposed through the acceptance
wrapper and invoked by final-lane preflight, with these properties:

```text
./tools/run-acceptance-platform.sh --maintenance retention \
  --state-root /srv/starlink-acceptance \
  --policy tools/acceptance/platform/retention-policy.toml
```

Standalone invocation defaults to report-only and requires `--apply` for
deletion. Final-lane preflight invokes the same command in apply mode before
allocating a new checkout, task root, browser, or Compose resources. Both modes
write a mode-0700, bounded JSON report below
`<state-root>/maintenance/retention/<UTC>-<UUID>/` containing:

- canonical state root and policy digest;
- run mode, start/end UTC timestamps, and tool version;
- protected candidate identity and the reason it is protected;
- each examined path, retention class, age, disposition, and reason;
- anomaly entries, candidate counts, and byte totals; and
- post-run verification of every deletion and retained protected authority.

The report is itself retention-managed: retain the newest 90 reports and prune
older valid reports. A report with malformed content or an unexpected path is
retained and reported rather than deleted.

The command validates all candidate paths with descriptor-based, no-follow
access beneath the canonical state root. It uses atomic rename-to-quarantine
inside that root before recursive deletion, verifies the quarantined path is no
longer discoverable, and records the final absence. An error in one candidate
must not expand scope; independent eligible entries may continue, while the
command exits nonzero if any anomaly or deletion error occurred.

### Cooperative runner ownership boundary

The configured acceptance state root is exclusively runner-controlled. The
maintenance command acquires a mode-0600, nonblocking exclusive lock beneath
that root before it plans or applies retention and holds that lock through
report sealing and every cleanup action. A concurrent repository-owned runner
that cannot acquire the lock fails closed and makes no cleanup mutation.

The lock serializes approved runner activity; it is not presented as a defense
against a malicious same-UID process deliberately bypassing the lock. That
process is outside this repository-owned lifecycle boundary. Descriptor/no-follow
checks, ownership validation, and all anomaly handling remain mandatory. A
future requirement to defend against a hostile same-UID writer needs a separate
privileged maintenance authority and approved design.

The command takes no caller-controlled arbitrary deletion path, remote-cache
control, force flag, volume option, or scheduler option. It must reject a policy
whose completed-generation count is not exactly three.

## Runner-owned checkout lifecycle

The final-lane wrapper creates its detached exact-SHA checkout only below an
explicit, canonical checkout root supplied by the approved host configuration.
At allocation it writes a mode-0600 regular ownership marker below the checkout
root containing the lane, exact SHA, ref, task identifier, creator version, and
creation timestamp. The marker is data, not authority to traverse outside the
canonical checkout root.

After the lane has sealed its evidence and completed runtime cleanup, the same
wrapper removes that marked checkout before reporting success, failure, or a
coverage gap. It must verify all of the following before removal:

1. the checkout and marker are regular no-follow descendants of the configured
   checkout root;
2. the marker identity matches the just-completed lane and exact SHA;
3. the checkout is detached at that exact SHA and has no tracked, staged, or
   untracked worktree changes; and
4. no task-owned process, Compose resource, or current working directory remains
   below the checkout.

Failure to remove the current runner-owned checkout is a cleanup failure and
downgrades the lane outcome. The wrapper records the failed deletion separately
without overwriting primary evidence.

The retention preflight also inventories marked completed checkouts from prior
interrupted lanes. It may remove only a marked checkout whose marker, detached
SHA, clean status, liveness checks, and root containment all validate. An
unmarked checkout, a marker mismatch, a non-detached checkout, a dirty checkout,
or an active process is retained and reported as an anomaly. This preserves
user-owned clones and historical/legacy workspaces even when they happen to live
near the configured checkout root.

## Operational lifecycle controls

Runner-owned Docker images/builders/workspaces, GitHub Actions build records, and
GHCR package inventory are governed by the
[Operational Controls](2026-09-27-acceptance-retention-operational-lifecycle.md)
companion. It preserves the fixed three-generation bound, keeps acceptance volumes
inventory-only, deletes only marked runner-owned Docker/workspace resources, and
keeps GHCR package retention report-only until deployment inventory is authoritative.

## Policy file

The tracked policy establishes the fixed retention bound:

```toml
version = 1
completed_generations_per_lane = 3
maintenance_report_count = 90
```

The policy cannot reduce protected-final retention or increase the completed
generation count. Policy parsing rejects unknown keys, duplicate keys,
non-integers, and unsafe values. The command writes the policy SHA-256 into every
report.

## Legacy local artifact handling

Existing Oracle-local evidence and SDD directories predate this policy and do
not share a single manifest/authority layout. The retention command inventories
but does not delete them automatically. It emits a legacy report grouping each
entry by path, size, modification time, recognizable manifest identity, and
whether it is referenced by an open PR or protected final authority.

An operator may later use a separately authorized migration or deletion command
command for a named legacy entry after reviewing that report. There is no bulk
"delete everything older than N days" path.

Existing unmarked host checkout/worktree directories are also legacy material:
the inventory reports their path, size, Git state when readable, and active
process association, but does not delete them automatically.

Existing unlabelled Docker images, shared builder cache, browser stores, and
GitHub package versions are likewise legacy or administrator-owned material. They
are included in inventory reports but excluded from automatic deletion.

New SDD workspaces created after this policy use a completion marker naming the
merged PR and merge commit. A local maintenance mode may remove only a marked,
merged workspace once it falls outside the three newest merged workspaces after
verifying it is not the current workspace of an open branch. Unmarked legacy SDD
directories remain report-only.

## Final-lane preflight and operations

The final-lane wrapper runs retention after exact candidate/ref validation but
before creating the new checkout, task root, browser, or Compose resources. It
uses the explicit state root and tracked policy, writes a durable report, and
fails closed on anomalies, ownership ambiguity, checksum failures, or deletion
errors. This makes the policy portable across Forge, a replacement host, or
another approved compute environment; no Forge-owned timer, daemon, or service
is installed.

The runbook requires inspection of the latest report, protected final identity,
anomalies, `docker ps` output, and available disk space when preflight fails. A
failed run or anomaly leaves data intact and requires investigation; it is not
retried with broader permissions.

## Testing and verification

Tests cover:

- policy parsing, fixed-generation enforcement, and unsafe-value rejection;
- protected-final selection and timestamp ambiguity fail-closed behavior;
- valid generation-count classification for final, health/static, logs, ledgers,
  and empty task parents;
- runner-owned checkout creation, normal post-lane removal, interrupted-lane
  inventory, and every marker, dirty-worktree, path-escape, or live-process
  refusal path;

- checksum, authority, manifest, symlink, path-escape, and unknown-content
  anomalies retaining data and returning nonzero;
- dry-run never deleting data;
- apply-mode quarantine, absence verification, and bounded report creation;
- active task-owned resource detection preventing parent cleanup; and
- legacy inventory remaining non-destructive.

Static verification runs the project verifier. A focused temporary state root
exercises both dry-run and apply modes without Docker, followed by an
independent review of the destructive-path safety properties. Documentation
validation includes markdownlint and link checks.

## Documentation impact

Update the acceptance-platform operations guide and the external-host final
acceptance runbook with generation retention, final-lane preflight, report review,
runner-owned checkout lifecycle, recovery behavior, and the prohibition on volume,
profile, user-owned repository, or unclassified legacy deletion. The companion
specifies the additional Docker, Actions, and GHCR documentation impact.
