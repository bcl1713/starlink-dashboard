#!/usr/bin/env bash
# Read-only future Forge inventory. Never builds/starts apps, browsers or traffic.
set -euo pipefail
cd "$(dirname "$0")"
case "${1:---offline}" in
  --offline)
    python3 -B - <<'PY'
import hashlib
import json
from pathlib import Path
root = Path.cwd()
manifest = json.loads((root / 'evidence/stage5/release-manifest.json').read_bytes())
for name, expected in manifest['files'].items():
    path = root / name
    if path.is_symlink() or root not in path.resolve().parents:
        raise SystemExit('invalid manifest path: ' + name)
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise SystemExit('hash mismatch: ' + name)
print(json.dumps({'verified_files': len(manifest['files']),
                  'qualification': manifest['qualification'],
                  'runtime_authorized': False}))
PY
    ;;
  --inspect-runtime)
    # Run only in a separately authorized runtime session. Preserve actor selection.
    printf 'Actor UID: %s\n' "$(id -u)"
    printf 'Actor runtime directory: %s\n' "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
    printf 'DOCKER_HOST configured: %s\n' "${DOCKER_HOST:+yes}"
    timeout --kill-after=5s 15s docker context show
    timeout --kill-after=5s 15s docker info --format '{{json .ServerVersion}} {{json .CgroupDriver}} {{json .CgroupVersion}} {{json .SecurityOptions}}'
    timeout --kill-after=5s 15s docker compose version
    node --version
    python3 --version
    # No browser launch or download; inspect a supplied existing installation only.
    : "${PERF391_NODE_ROOT:?set the reviewed existing Playwright installation directory}"
    PERF391_NODE_ROOT="$PERF391_NODE_ROOT" node - <<'JS'
const { createRequire } = require('node:module');
const req = createRequire(process.env.PERF391_NODE_ROOT + '/package.json');
const { existsSync, readFileSync } = require('node:fs');
const { createHash } = require('node:crypto');
const browser = req('playwright').chromium.executablePath();
if (!existsSync(browser)) throw Error('reviewed Chromium binary absent');
console.log(JSON.stringify({playwright: req('playwright/package.json').version,
  browser, sha256: createHash('sha256').update(readFileSync(browser)).digest('hex')}));
JS
    cat /proc/self/cgroup
    readlink /proc/self/ns/pid /proc/self/ns/net /proc/self/ns/mnt
    cat /proc/sys/kernel/random/boot_id
    # These are inventory reads, not port reservation or capture permission checks.
    ss -ltn
    for role in A C; do
      if [[ "$role" == A ]]; then image="${PERF391_A_IMAGE:-}"; else image="${PERF391_C_IMAGE:-}"; fi
      [[ "$image" =~ ^sha256:[0-9a-f]{64}$ ]] || { printf 'Missing immutable %s diagnostic image ID\n' "$role" >&2; exit 2; }
      timeout --kill-after=5s 15s docker image inspect "$image" --format '{{json .Id}} {{json .RepoDigests}} {{json .Config.Labels}}'
    done
    printf '%s\n' 'Inventory only. Match images/assets/labels and host mappings to the reviewed runtime manifest before a separate short-run GO. Stage 3B remains deferred.'
    ;;
  *) printf 'Usage: %s --offline | --inspect-runtime\n' "$0" >&2; exit 2 ;;
esac
