# Phase 0: Contract and Branch Reset

## Identity and objective

Repository `bcl1713/starlink-dashboard`, durable PR
`https://github.com/bcl1713/starlink-dashboard/pull/143`, base `dev`, feature
`feature/react-operations-overview`. Historical head is
`e649ce169cd5adcbdd83d6264290b30d5221599e`; reset baseline is
`07593c69040ad447000bf526d6453ec5c6faacfa`; expected archive is
`archive/pr-143-pre-simplification-e649ce1`.

Create an executable docs-only contract from current `dev`. Oracle, not the
writer, archives the old remote head and publishes the exact reviewed candidate.
No production implementation begins in this phase.

## Scope

**In:** exactly the master roadmap and seven supporting files under
`docs/plans/react-operations-overview-rebuild/`; relative links, phase gates,
checks, and concrete Phase 1 handoff inputs.

**Out:** production/test/config/package changes, old plan copies, Docker,
GitHub/PR edits, pushes, archive/ref creation, and Phase 1 implementation.

The binding product contract is [the product contract](00-product-contract.md).
The old implementation is historical only; selective future salvage requires
deliberate review and never a wholesale cherry-pick.

## Likely paths

There are no advisory code paths in this docs-only phase. These paths are exact:

- `docs/plans/2026-09-02-react-operations-overview-rebuild.md`
- `docs/plans/react-operations-overview-rebuild/00-product-contract.md`
- `docs/plans/react-operations-overview-rebuild/01-phase-0-contract-reset.md`
- `docs/plans/react-operations-overview-rebuild/02-phase-1-live-data.md`
- `docs/plans/react-operations-overview-rebuild/03-phase-2-fullscreen-layout.md`
- `docs/plans/react-operations-overview-rebuild/04-phase-3-runtime-acceptance.md`
- `docs/plans/react-operations-overview-rebuild/05-phase-4-docs-and-integration.md`
- `docs/plans/react-operations-overview-rebuild/SESSION-HANDOFF.md`

## Bounded task order

**TDD expectation:** Phase 0 has no production code cycle. Treat formatting,
lint, link/anchor, line-limit, and exact-path validators as executable contract
tests: observe any failure, correct only the docs, and rerun before commit.

1. Verify clean branch `phase0/pr143-contract-reset`; initial authoring starts
   at the exact baseline SHA and any reviewed correction starts at its exact
   blocked candidate while preserving the baseline as ancestor.
2. Inspect repository naming, Markdown, line-size, and existing command policy.
3. Author only the eight paths above; keep each file at or below 300 lines.
4. Run Prettier in write mode only on those eight files, then check mode.
5. Run markdownlint only on those eight files.
6. Programmatically validate every relative Markdown target and heading anchor.
7. Run `git diff --check`, roadmap-marker validation, line counts, and exact
   changed-path assertions against the fixed baseline SHA.
8. Commit once with `docs(plan): reset React overview implementation phases`.
9. Verify clean worktree. The initial commit's parent equals the baseline; a
   superseding correction's parent equals the blocked candidate. In either case,
   the baseline diff contains only the eight paths. Hand the immutable SHA to
   Oracle.
10. Oracle arranges independent specification review, then documentation-quality
    review. Reviewers must not edit this worktree.
11. If review changes are needed, the sole writer adds a superseding local
    commit, reruns every check, and hands Oracle the new immutable SHA. For the
    nine-finding correction to blocked candidate
    `1b0cbd51e66e03d654b75f2fa3b54ebbe760befd`, use exactly
    `docs(plan): close overview rebuild contract gaps`.
12. For the executable-mechanics correction to blocked candidate
    `09c4b678927e63bbc7a9417cad6e59a9dcf1606c`, preserve both prior commits and
    use exactly `docs(plan): make rebuild gates fail closed`.

## Checks and expected results

The formatter/linter/link commands are the focused checks for changed docs. The
diff, line-count, and exact-path commands form the full Phase 0 gate.

Use these copy-pasteable commands from the repository root. Bounded `npx --yes`
may use its external cache but must not change package or lock files:

```bash
set -euo pipefail
BASE=07593c69040ad447000bf526d6453ec5c6faacfa
DOCS=(
  docs/plans/2026-09-02-react-operations-overview-rebuild.md
  docs/plans/react-operations-overview-rebuild/00-product-contract.md
  docs/plans/react-operations-overview-rebuild/01-phase-0-contract-reset.md
  docs/plans/react-operations-overview-rebuild/02-phase-1-live-data.md
  docs/plans/react-operations-overview-rebuild/03-phase-2-fullscreen-layout.md
  docs/plans/react-operations-overview-rebuild/04-phase-3-runtime-acceptance.md
  docs/plans/react-operations-overview-rebuild/05-phase-4-docs-and-integration.md
  docs/plans/react-operations-overview-rebuild/SESSION-HANDOFF.md
)
npx --yes prettier@3.6.2 --write "${DOCS[@]}"
npx --yes prettier@3.6.2 --check "${DOCS[@]}"
npx --yes markdownlint-cli2@0.19.1 "${DOCS[@]}"
git diff --check "$BASE"...HEAD
wc -l "${DOCS[@]}"
test "$(git diff --name-only "$BASE"...HEAD | sort)" = \
  "$(printf '%s\n' "${DOCS[@]}" | sort)"
test "$(git ls-files -- \
  docs/plans/2026-09-02-react-operations-overview-rebuild.md \
  docs/plans/react-operations-overview-rebuild | sort)" = \
  "$(printf '%s\n' "${DOCS[@]}" | sort)"
if git diff --name-only "$BASE"...HEAD | grep -Eq \
  '(^|/)2026-08-29-react-operations-overview|react-operations-overview/'; then
  echo "retired overview path remains" >&2
  exit 1
fi
```

Run this exact relative-link and GitHub-style heading-anchor validator:

```bash
python3 - "${DOCS[@]}" <<'PY'
import re
import sys
import urllib.parse
from collections import Counter
from pathlib import Path

docs = [Path(value) for value in sys.argv[1:]]
errors = []

def slugify(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value.strip().lower())
    value = re.sub(r"[^\w\- ]", "", value, flags=re.UNICODE)
    return re.sub(r"[ ]+", "-", value)

def anchors(path: Path) -> set[str]:
    counts: Counter[str] = Counter()
    found: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if not match:
            continue
        base = slugify(match.group(1))
        number = counts[base]
        counts[base] += 1
        found.add(base if number == 0 else f"{base}-{number}")
    return found

for source in docs:
    text = source.read_text(encoding="utf-8")
    for raw in re.findall(r"(?<!!)\[[^]]*\]\(([^)]+)\)", text):
        destination = raw.strip().split(maxsplit=1)[0].strip("<>")
        parsed = urllib.parse.urlsplit(destination)
        if parsed.scheme or parsed.netloc or destination.startswith("/"):
            continue
        target_text = urllib.parse.unquote(parsed.path)
        target = source if not target_text else (source.parent / target_text)
        target = target.resolve()
        if target.is_dir():
            target = target / "README.md"
        if not target.is_file():
            errors.append(f"{source}: missing target {destination}")
            continue
        if parsed.fragment:
            fragment = urllib.parse.unquote(parsed.fragment).lower()
            if fragment not in anchors(target):
                errors.append(f"{source}: missing anchor {destination}")

print(f"checked_files={len(docs)} errors={len(errors)}")
if errors:
    print(*errors, sep="\n")
    raise SystemExit(1)
PY
```

Run this exact roadmap-marker validator:

```bash
python3 - <<'PY'
from pathlib import Path

root = Path("docs/plans")
roadmap = (root / "2026-09-02-react-operations-overview-rebuild.md").read_text()
required = [
    "## Authority and precedence",
    "## Delivery model and branch policy",
    "## Phase sequence and hard boundaries",
    "01-phase-0-contract-reset.md",
    "02-phase-1-live-data.md",
    "03-phase-2-fullscreen-layout.md",
    "04-phase-3-runtime-acceptance.md",
    "05-phase-4-docs-and-integration.md",
    "SESSION-HANDOFF.md",
]
missing = [marker for marker in required if marker not in roadmap]
print(f"roadmap_markers={len(required)} missing={len(missing)}")
if missing:
    print(*missing, sep="\n")
    raise SystemExit(1)
PY
```

Exact path verification must compare a sorted generated list against the eight
listed paths, not rely on visual inspection. Confirm no retired old-plan file
and no production, test, config, package, lock, or Compose file appears.

A check-only pre-commit invocation is optional only when it can be constrained
to these files and will not mutate unrelated files. Do not use a fixer-bearing
all-files run for a documentation-only candidate. The repository filename
checker currently rejects the required uppercase status/session filename
`SESSION-HANDOFF.md`, contrary to `AGENTS.md`; omit that checker and rely on the
exact eight-path assertion above until the checker honors the repository rule.

## Review gate and public handoff

**Specification review:** independently compare every roadmap requirement,
identity/ref/SHA, phase boundary, security rule, retired gate, and handoff
field. Disposition is `PASS` or a finite findings list.

**Quality review:** after spec passes, independently check navigability,
self-contained session startup, actionable task sizes, unambiguous stop gates,
formatting, and duplication. Disposition is `PASS` or findings.

The Phase 0 public PR handoff, posted by Oracle, must state:

- PR/base/feature, exact candidate SHA, baseline and historical SHA;
- archive ref and the guarded publication procedure: verify the remote feature
  is still the historical SHA, create/push/read back the archive before reset,
  then use force-with-lease explicitly tied to that historical SHA;
- eight changed paths, docs-only impact, and commands/results;
- spec/quality dispositions and unresolved questions;
- confirmation that no push/GitHub/Docker action occurred in the writer session;
- `next_step`: after archive readback, guarded-force-update the feature ref,
  read back the candidate SHA, verify the remote baseline diff has exactly the
  eight paths, then open Phase 1. Unguarded force push is forbidden.

## Documentation impact, cleanup, and completion

Documentation impact is this roadmap only; no operator/user behavior changed.
Remove any formatter cache or temporary validator artifact. Local-writer
completion requires the bounded local commit, clean status, correct parent for
initial or superseding work, baseline ancestry, exact eight-file baseline diff,
and all checks green. Oracle may publish only after independent specification
then quality approval of that immutable commit.

Stop after handoff. Phase 1 input is the Oracle-published Phase 0 SHA, not the
local baseline and not a guessed value. Phase 1 output is defined in
[Phase 1](02-phase-1-live-data.md).
