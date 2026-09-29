<!-- markdownlint-disable MAX_LINES -->

# External-Host Final Acceptance

Use this runbook when the Oracle host cannot provide the required Linux browser,
Docker, or display capacity. The external Linux host is the final-lane authority
for this candidate. It does not inherit Oracle's browser profile: absolute paths
and provenance are host-specific.

This procedure has two roles:

- A platform administrator provisions Chromium and creates the host-local profile.
- A branch operator checks out the exact candidate, runs health and static, then
  runs one final lane.

Do not copy personal credentials, `.env` files, browser profiles, evidence, or
browser bundles from Oracle. The repository's default profile is deliberately
unprovisioned and must remain so.

## Boundaries and variables

Run every group from the external host. Choose host-local paths outside the
candidate repository. Keep the evidence and task paths on durable local storage.
All task and evidence paths below include the candidate SHA; use a new task root
for every attempt.

```bash
BRANCH=feat/v2-mission-retirement
REF=refs/heads/feat/v2-mission-retirement
HOST_STATE=${STARLINK_ACCEPTANCE_ROOT:-$HOME/starlink-acceptance}
CHECKOUT_ROOT=$HOST_STATE/tasks/checkouts
RUNNER_CHECKOUT_ROOT=$HOST_STATE/runner-checkouts
PROFILE=/srv/starlink-acceptance/profiles/v2-mission-retirement-chromium.toml
CONTRACT=tools/acceptance/contracts/v2-mission-retirement.toml
HEALTH_EVIDENCE_ROOT=$HOST_STATE/evidence/health
STATIC_EVIDENCE_ROOT=$HOST_STATE/evidence/static
FINAL_EVIDENCE_ROOT=$HOST_STATE/evidence/final
LOG_ROOT=$HOST_STATE/logs
PYTHON_ENV=$HOST_STATE/tasks/python-env
```

The host needs Git, Node/npm, Docker with the Compose plugin, Xvfb, Python 3,
`uv`, the repository's frontend dependencies, `markdownlint-cli2`, and Lychee.
Do not substitute a caller browser session or a deployed origin for the runner's
owned browser and loopback origin.

Before checkout, select a durable worker-owned `HOST_STATE` (override the example
with `STARLINK_ACCEPTANCE_ROOT` if necessary). Do not assume
`/srv/starlink-acceptance/checkouts` is writable. The immutable `PROFILE` is an
administrator-provisioned host-local input, not a worker-created file. Stop if
any allocation root cannot be created or written by the branch operator:

```bash
mkdir -p "$HOST_STATE" || exit 1
for root in "$HOST_STATE" "$CHECKOUT_ROOT" "$RUNNER_CHECKOUT_ROOT" \
  "$HEALTH_EVIDENCE_ROOT" "$STATIC_EVIDENCE_ROOT" "$FINAL_EVIDENCE_ROOT" \
  "$HOST_STATE/tasks" "$HOST_STATE/state" "$HOST_STATE/ledgers/final" \
  "$LOG_ROOT"; do
  mkdir -p "$root" && test -w "$root" || exit 1
done
test -r "$PROFILE" || exit 1
```

## 1. Obtain a fresh, detached exact-SHA candidate

Fetch the named remote branch into a new clone or disposable checkout. Do not
accept a local branch name, a short SHA, or a ref whose remote target differs
from the requested candidate.

```bash
git clone --no-checkout https://github.com/bcl1713/starlink-dashboard.git \
  "$CHECKOUT_ROOT/v2-mission-retirement"
cd "$CHECKOUT_ROOT/v2-mission-retirement"
git fetch --no-tags origin \
  "+refs/heads/$BRANCH:refs/remotes/origin/$BRANCH"
SHA=$(git rev-parse "origin/$BRANCH^{commit}")
git checkout --detach "$SHA"
test "$REF" = "refs/heads/$BRANCH" || exit 1
test "$(git rev-parse HEAD)" = "$SHA" || exit 1
test "$(git rev-parse "refs/remotes/origin/$BRANCH^{commit}")" = "$SHA" || exit 1
# The final wrapper resolves the named ref locally, not origin/$BRANCH.
# Refuse a pre-existing local ref rather than silently moving it.
if git show-ref --verify --quiet "$REF"; then
  test "$(git rev-parse "$REF^{commit}")" = "$SHA" || exit 1
else
  git update-ref "$REF" "$SHA" "0000000000000000000000000000000000000000" || exit 1
fi
test "$(git rev-parse "$REF^{commit}")" = "$SHA" || exit 1
test -f "$CONTRACT" || exit 1
printf 'HEAD=%s\nREMOTE=%s\nREF=%s\n' \
  "$(git rev-parse HEAD)" "$(git rev-parse "origin/$BRANCH^{commit}")" "$REF"
```

**Stop** unless `HEAD`, `REMOTE`, and the local named `REF` are the same full
40-character SHA. Preserve
that printed SHA as `SHA`; the runner requires lowercase full SHA and named ref.
Record the commit's signed/reviewed identity according to local release policy.

Install the candidate's locked frontend dependencies before health. From the
checked-out candidate:

```bash
cd frontend/mission-planner
env CI=1 npm ci --ignore-scripts
cd ../..
```

This prepares the health card, ESLint, and Vitest from the committed lockfile.
`--ignore-scripts` prevents branch-controlled lifecycle scripts from acting as
a Playwright or Chromium installer. Do not substitute `npm install`, `npx`, a
browser installer, or a pre-existing checkout's `node_modules` directory.
The final runner prepares its own fresh worktree's frontend with
`npm ci --ignore-scripts`; do not change that separate lifecycle.

Bootstrap task-owned host Python before the static verifier or any lane. Forge's
`/usr/bin/python3` may have no pip or pytest; `./tools/verify static` runs
`python3 -m pytest` and the runner imports `yaml`. The PyYAML requirement is
declared in `backend/starlink-location/requirements.txt` as `PyYAML>=6.0`.
Keep the environment outside the candidate; do not install into system Python.

```bash
uv venv --python python3 "$PYTHON_ENV"
uv pip install --python "$PYTHON_ENV/bin/python" pytest 'PyYAML>=6.0'
export PATH="$PYTHON_ENV/bin:$PATH"
test "$(command -v python3)" = "$PYTHON_ENV/bin/python3" || exit 1
PYTHONPATH="$PWD/tools${PYTHONPATH:+:$PYTHONPATH}" python3 -c \
  'import pytest, yaml, acceptance.platform.runner'
```

**Stop** if the imports fail or `python3` does not resolve into this task-owned
environment. Keep this `PATH` for the verifier and all lane invocations.

## 2. Administrator-only Chromium provisioning

This is a one-time host administration action, not a branch-final action. Use a
separate, administrator-owned provisioning task root and browser store. The
provisioner requires all six flags shown here, including the explicit npm binary.

```bash
cd "$CHECKOUT_ROOT/v2-mission-retirement"
ADMIN_STATE=/srv/starlink-acceptance
BROWSER_ROOT=$ADMIN_STATE/browser-store
PROVISION_TASK_ROOT=$ADMIN_STATE/provisioning/v2-mission-retirement
PROVENANCE_FILE=$PROVISION_TASK_ROOT/provenance.json
NPM_EXECUTABLE=$(realpath "$(command -v npm)")
mkdir -p "$BROWSER_ROOT" "$PROVISION_TASK_ROOT"
node tools/acceptance/browser/provision-v2-mission-retirement-chromium.mjs \
  --mode provision \
  --project-dir "$PWD/frontend/mission-planner" \
  --browser-root "$BROWSER_ROOT" \
  --task-root "$PROVISION_TASK_ROOT" \
  --provenance-file "$PROVENANCE_FILE" \
  --npm-executable "$NPM_EXECUTABLE"
```

**Stop** if this exits nonzero or its JSON status is not `passed`. Do not use
`npx`, inherited `PATH` resolution, a system Chromium, or a browser copied from
another host. Retain the 0600 provenance file under host administration control.

## 3. Administrator creates the immutable host-local profile

Repository tooling writes provisioning provenance but does **not** generate or
sign a profile descriptor. Therefore an administrator, not a branch operator,
must manually create and approve an immutable TOML descriptor outside the
candidate repository.

The descriptor has exactly these fields:

```toml
version = "<administrator-assigned immutable profile version>"
checksum = "<administrator-recorded 64-lowercase-hex profile checksum>"

[browser]
store_root = "<absolute browserRoot from provenance>"
executable = "<absolute executable.path from provenance>"
version = "<executable.versionOutput from provenance>"
byte_size = <executable.size from provenance>
sha256 = "<executable.sha256 from provenance>"
```

Populate the browser fields from the successful provenance's `browserRoot` and
`executable` object, without changing values. The profile's `checksum` is an
administrator-controlled immutable-record value: the repository supplies no
profile-checksum generation or signing mechanism, so do not invent one from
ad hoc shell text or claim a computed descriptor checksum is authenticated.

Before approving the profile, the administrator must validate all of the
following against the provenance and live host: both browser paths are absolute;
the executable is a non-symlink regular executable below `store_root`; its
`--version` output equals `browser.version`; and its byte size and SHA-256 equal
`browser.byte_size` and `browser.sha256`. The profile checksum must be exactly
64 lowercase hexadecimal characters and must match the administrator's immutable
profile record. Keep the descriptor and record host-local, access-controlled,
and unchanged during the candidate run.

**Stop** if any value differs. A health `environment_blocked` outcome here is a
host/provisioning failure, not a product failure.

## 4. Install the CI-pinned link checker

Install Lychee 0.20.1 once on the external host. The CI pin is exact; a different
installed version is not equivalent evidence.

```bash
cargo install --locked lychee --version 0.20.1
lychee --version
```

**Stop** unless the version output identifies `lychee 0.20.1`. If Cargo is not
available, install the same 0.20.1 release through the host's approved package
channel, then repeat the version check. Do not continue with an unpinned Lychee.

## 5. Run static at the candidate base

Set the policy base from the fetched `origin/dev` and verify it before invoking
the repository verifier.

```bash
cd "$CHECKOUT_ROOT/v2-mission-retirement"
git fetch --no-tags origin "+refs/heads/dev:refs/remotes/origin/dev"
BASE_SHA=$(git merge-base origin/dev HEAD)
git cat-file -e "${BASE_SHA}^{commit}"
git merge-base --is-ancestor "$BASE_SHA" HEAD
ACCEPTANCE_POLICY_BASE_SHA="$BASE_SHA" ./tools/verify static
```

**Stop** on any nonzero result. This verifies the complete repository static tier;
it is not final acceptance.

## 5a. Retention maintenance is report-first and separate from a final lane

Run maintenance only with the external host's repository-owned state and
checkout roots. It is not a way to repair a failed health, static, or final lane.
First generate and retain a report-only JSON result; the [platform operations
runbook](acceptance-platform.md#retention-maintenance) is the detailed authority:

```bash
set -o pipefail
STATE_ROOT=$HOST_STATE/state
CHECKOUT_RECOVERY_ROOT=$RUNNER_CHECKOUT_ROOT
./tools/run-acceptance-platform.sh --maintenance retention \
  --state-root "$STATE_ROOT" \
  --policy tools/acceptance/platform/retention_policy.toml \
  --checkout-root "$CHECKOUT_RECOVERY_ROOT" \
  | tee "$LOG_ROOT/retention-report-$(date -u +%Y%m%dT%H%M%SZ).json"
```

Before an apply operation, inspect the protected final candidate, proposed
deletions, anomalies, scoped `docker ps` output, and free disk space. Stop on an
anomaly, unavailable lease, malformed report, or nonzero exit. Confirm mode,
planned deletions, reclaimed-byte estimate, post-action status, and anomaly count.

Only after that documented review may the operator add `--apply` to the exact
same command and retain the resulting JSON. The policy preserves the protected
latest final authority plus two newer completed generations per lane. The tool
may remove only policy-selected sealed evidence and exact, fully runner-owned,
unreferenced Docker image IDs. Never run `docker system prune`, `docker image
prune`, `docker volume prune`, `git clean`, `git gc`, or broad deletion commands;
volumes are inventory-only and must not be deleted.

Checkout recovery is equally narrow. It removes a checkout only when a regular
mode-0600 runner marker, exact detached SHA, clean worktree, and inactive exact
`--acceptance-task` process all validate. Missing marker, symlink, liveness,
authority, SHA, or cleanliness ambiguity is a retained anomaly; investigate it
without manual deletion.

The GitHub Actions retention job is the only Actions artifact lifecycle here: it
uses complete pagination and completion-time ordering, preserves the current run
and two newer completed runs, and deletes only selected `dockerbuild` artifact
IDs. It never deletes workflow runs, releases, or arbitrary artifacts. GHCR is
inventory-only: never delete GHCR versions from this runbook or the workflow.
GHCR `updated_at` is mutable ordering metadata, not publish-completion authority,
so every SHA-only version remains retained and the inventory reports that gap
until an authoritative completion field exists.

## 6. Certify health and verify its canonical authority

Create separate SHA-qualified task roots. The health fingerprint is canonical
only at `<health-evidence-root>/<sha>/fingerprint.json`; do not use a
`candidates/.discoverable` envelope as health authority.

```bash
HEALTH_ATTEMPT_ID="health-$SHA-$(python3 -c 'import uuid; print(uuid.uuid4().hex)')"
HEALTH_TASK_ROOT=$HOST_STATE/tasks/health/$SHA-$HEALTH_ATTEMPT_ID
mkdir -p "$HEALTH_TASK_ROOT"
test ! -e "$HEALTH_EVIDENCE_ROOT/$SHA" || exit 1
./tools/run-acceptance-platform.sh \
  --lane health \
  --sha "$SHA" \
  --ref "$REF" \
  --profile "$PROFILE" \
  --contract "$CONTRACT" \
  --acceptance-task "$HEALTH_ATTEMPT_ID" \
  --evidence-root "$HEALTH_EVIDENCE_ROOT" \
  --task-root "$HEALTH_TASK_ROOT" || exit 1

HEALTH_FINGERPRINT=$HEALTH_EVIDENCE_ROOT/$SHA/fingerprint.json
PYTHONPATH="$PWD/tools${PYTHONPATH:+:$PYTHONPATH}" python3 - \
  "$HEALTH_FINGERPRINT" "$PROFILE" <<'PY'
import json, sys
from pathlib import Path
from acceptance.platform.health import validate_fingerprint
from acceptance.platform.runner import _load_profile
fingerprint = validate_fingerprint(_load_profile(Path(sys.argv[2])), Path(sys.argv[1]))
print(json.dumps(fingerprint.to_dict(), sort_keys=True))
PY
```

**Stop** unless the health command and fingerprint validation both pass and the
sealed fingerprint reports `outcome` `passed`, the expected profile checksum,
and the expected browser identity. Preserve the fingerprint path for later
lanes; do not replace it with a candidate envelope.

## 7. Run the tracked static lane

The runner's static lane revalidates the sealed health fingerprint before it
starts contract checks. It has its own evidence and task roots.

```bash
STATIC_ATTEMPT_ID="static-$SHA-$(python3 -c 'import uuid; print(uuid.uuid4().hex)')"
STATIC_TASK_ROOT=$HOST_STATE/tasks/static/$SHA-$STATIC_ATTEMPT_ID
mkdir -p "$STATIC_TASK_ROOT"
test ! -e "$STATIC_EVIDENCE_ROOT/candidates/$SHA" || exit 1
./tools/run-acceptance-platform.sh \
  --lane static \
  --sha "$SHA" \
  --ref "$REF" \
  --profile "$PROFILE" \
  --contract "$CONTRACT" \
  --acceptance-task "$STATIC_ATTEMPT_ID" \
  --fingerprint "$HEALTH_FINGERPRINT" \
  --evidence-root "$STATIC_EVIDENCE_ROOT" \
  --task-root "$STATIC_TASK_ROOT" || exit 1

STATIC_CANDIDATE_ROOT=$STATIC_EVIDENCE_ROOT/candidates/$SHA
PYTHONPATH="$PWD/tools${PYTHONPATH:+:$PYTHONPATH}" python3 - \
  "$STATIC_CANDIDATE_ROOT" "$SHA" "$REF" "$HEALTH_FINGERPRINT" <<'PY'
import hashlib, json, sys
from pathlib import Path
from acceptance.platform.evidence import read_fingerprint_authority, read_nofollow, verify_manifest
candidate = Path(sys.argv[1]); sha, ref, health_path = sys.argv[2:]
verify_manifest(candidate)
runner_manifest = read_nofollow(candidate / "runner-manifest.json")
manifest = json.loads(runner_manifest)
if (manifest.get("lane"), manifest.get("outcome"), manifest.get("final_acceptance"),
    manifest.get("sha"), manifest.get("ref")) != ("static", "passed", False, sha, ref):
    raise SystemExit("sealed static runner manifest does not match this candidate")

expected = {"sha": sha, "ref": ref,
    "health_fingerprint_sha256": hashlib.sha256(read_nofollow(Path(health_path))).hexdigest(),
    "runner_manifest_sha256": hashlib.sha256(runner_manifest).hexdigest()}
if json.loads(read_fingerprint_authority(candidate)) != expected:
    raise SystemExit("candidate fingerprint envelope does not bind this static run")
print("sealed passed static authority verified")
PY
```

Static authority lives under `candidates/<sha>`, unlike the health fingerprint
under `<health-evidence-root>/<sha>`. **Stop** on any nonzero result or non-passed
sealed static outcome. Do not repair a health or static failure by launching a
final lane.

## 8. Run exactly one final lane

Use one tracked process and an 1800-second budget. Final evidence, task root,
and build ledger must be distinct from health and static. Do not pass
`--browser-session` or `--deployed-origin`; the runner owns its Xvfb, browser,
CDP endpoint, task profile, and loopback frontend origin.

```bash
FINAL_ATTEMPT_ID="$(date -u +%Y%m%dT%H%M%SZ)-$(python3 -c 'import uuid; print(uuid.uuid4().hex)')"
FINAL_TASK_ROOT=$HOST_STATE/tasks/final/$SHA-$FINAL_ATTEMPT_ID
FINAL_LEDGER_ROOT=$HOST_STATE/ledgers/final/$SHA
mkdir -p "$FINAL_LEDGER_ROOT" "$LOG_ROOT" "$RUNNER_CHECKOUT_ROOT"
timeout --foreground --signal=TERM --kill-after=30s 1800s \
  ./tools/run-acceptance-platform.sh \
  --lane final \
  --sha "$SHA" \
  --ref "$REF" \
  --profile "$PROFILE" \
  --contract "$CONTRACT" \
  --fingerprint "$HEALTH_FINGERPRINT" \
  --evidence-root "$FINAL_EVIDENCE_ROOT" \
  --state-root "$FINAL_EVIDENCE_ROOT" \
  --policy tools/acceptance/platform/retention_policy.toml \
  --checkout-root "$RUNNER_CHECKOUT_ROOT" \
  --acceptance-task "$FINAL_ATTEMPT_ID" \
  --task-root "$FINAL_TASK_ROOT" \
  --ledger-root "$FINAL_LEDGER_ROOT" \
  2>&1 | tee "$LOG_ROOT/final-$SHA-$FINAL_ATTEMPT_ID.log"
FINAL_STATUS=${PIPESTATUS[0]}
printf 'final exit=%s\n' "$FINAL_STATUS"
```

**Stop** after this one final invocation regardless of result. Never silently
retry a final lane. Classify profile, browser, Xvfb, Docker, provisioning, or
health failure as host/provisioning; call a post-validation failure a product
failure only when sealed static, control, journey, build, or cleanup evidence
supports it. A new attempt requires explicit authorization, fresh health/static,
a new task root, and a recorded retry budget.

## 9. Inspect publication and cleanup

Only a passed final lane with sealed, published evidence and cleanup can claim
final acceptance. Its candidate envelope binds SHA/ref and health/runner digests,
but it is not the outcome authority. Verify the candidate root, require its sealed
runner manifest to claim passed final acceptance, then verify discovery authority.

```bash
FINAL_CANDIDATE_ROOT=$FINAL_EVIDENCE_ROOT/candidates/$SHA
FINAL_DISCOVERY_ROOT=$FINAL_EVIDENCE_ROOT/candidates/.discoverable/$SHA
PYTHONPATH="$PWD/tools${PYTHONPATH:+:$PYTHONPATH}" python3 - \
  "$FINAL_CANDIDATE_ROOT" "$FINAL_DISCOVERY_ROOT" "$SHA" "$REF" "$HEALTH_FINGERPRINT" <<'PY'
import hashlib, json, os, sys
from pathlib import Path
from acceptance.platform.evidence import read_fingerprint_authority, read_nofollow, verify_manifest
candidate, discovery = map(Path, sys.argv[1:3]); sha, ref = sys.argv[3:5]
health_fingerprint = Path(sys.argv[5])
verify_manifest(candidate)
runner_manifest = read_nofollow(candidate / "runner-manifest.json")
manifest = json.loads(runner_manifest)
if manifest.get("outcome") != "passed" or manifest.get("final_acceptance") is not True:
    raise SystemExit("sealed runner manifest does not claim passed final acceptance")
expected_candidate = {"sha": sha, "ref": ref, "health_fingerprint_sha256": hashlib.sha256(read_nofollow(health_fingerprint)).hexdigest(), "runner_manifest_sha256": hashlib.sha256(runner_manifest).hexdigest()}
if json.loads(read_fingerprint_authority(candidate)) != expected_candidate:
    raise SystemExit("candidate fingerprint envelope does not bind this final run")
if os.path.lexists(candidate.parent / ".revoked" / sha):
    raise SystemExit("candidate has a revocation entry")
verify_manifest(discovery)
sealed_authority = read_fingerprint_authority(discovery)
if sealed_authority != read_nofollow(discovery / "candidate-authority.json"):
    raise SystemExit("candidate-authority.json is not the sealed discovery authority")
expected = {"sha": sha, "runner_manifest_sha256": hashlib.sha256(runner_manifest).hexdigest()}
if json.loads(sealed_authority) != expected:
    raise SystemExit("discoverable authority does not bind this runner manifest")
print("sealed passed final authority verified")
PY
docker ps --filter "label=com.docker.compose.project=accept-${SHA:0:12}"
pgrep -af "$FINAL_TASK_ROOT" || true
pgrep -af "Xvfb|chrome|chromium" || true
test ! -e "$FINAL_TASK_ROOT"
```

**Stop** unless both manifests validate; the candidate envelope binds exactly
the SHA/ref and raw health and runner-manifest digests; the runner manifest
reports `outcome` `passed` and `final_acceptance` true; the sealed discoverable
`candidate-authority.json` binds exactly the SHA and raw runner-manifest SHA-256;
and no revocation entry exists. Require empty filtered Docker and task-root
process queries, an absent task root, and sealed cleanup/browser/Xvfb evidence;
the broad process listing is an audit aid and may show unrelated host processes.
Do not remove persistent volumes unless separately authorized.

Record the SHA/ref, host identity, profile version/checksum, health fingerprint
path, static result, final log, manifest path, and cleanup evidence.
