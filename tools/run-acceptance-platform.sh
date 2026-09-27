#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
export PYTHONPATH="$repo_root/tools${PYTHONPATH:+:$PYTHONPATH}"

if [[ ${1:-} == --maintenance ]]; then
  shift
  if [[ ${1:-} != retention ]]; then
    printf 'unsupported maintenance command\n' >&2
    exit 2
  fi
  exec python3 -m acceptance.platform.maintenance "$@"
fi

lane= sha= ref= state_root= policy= checkout_root= task=
runner_args=()
while (($#)); do
  case "$1" in
    --lane|--sha|--ref)
      [[ $# -ge 2 ]] || { printf 'missing value for %s\n' "$1" >&2; exit 2; }
      case "$1" in
        --lane) lane=$2 ;;
        --sha) sha=$2 ;;
        --ref) ref=$2 ;;
      esac
      runner_args+=("$1" "$2")
      shift 2
      ;;
    --state-root|--policy|--checkout-root|--acceptance-task)
      [[ $# -ge 2 ]] || { printf 'missing value for %s\n' "$1" >&2; exit 2; }
      case "$1" in
        --state-root) state_root=$2 ;;
        --policy) policy=$2 ;;
        --checkout-root) checkout_root=$2 ;;
        --acceptance-task)
          task=$2
          runner_args+=("$1" "$2")
          ;;
      esac
      shift 2
      ;;
    *)
      runner_args+=("$1")
      shift
      ;;
  esac
done

if [[ $lane != final ]]; then
  exec python3 -m acceptance.platform.runner "${runner_args[@]}"
fi

[[ $sha =~ ^[0-9a-f]{40}$ ]] || { printf 'final lane requires an exact SHA\n' >&2; exit 2; }
[[ $ref =~ ^refs/heads/[A-Za-z0-9._/-]+$ && $ref != *..* ]] || {
  printf 'final lane requires a safe branch ref\n' >&2
  exit 2
}
[[ -n $state_root && -n $policy && -n $checkout_root && -n $task ]] || {
  printf 'final lane requires state, policy, checkout root, and task identity\n' >&2
  exit 2
}
[[ $task =~ ^[A-Za-z0-9._-]+$ ]] || { printf 'invalid acceptance task identity\n' >&2; exit 2; }

# Bind the requested SHA/ref before maintenance or allocation can act.
[[ $(git -C "$repo_root" rev-parse "$ref") == "$sha" ]] || {
  printf 'final lane SHA/ref mismatch\n' >&2
  exit 2
}
checkout_root=$(cd "$checkout_root" && pwd -P)
state_root=$(cd "$state_root" && pwd -P)

# This runs before a checkout, task root, browser, or Compose resource exists.
python3 -m acceptance.platform.maintenance retention \
  --state-root "$state_root" --policy "$policy" --apply --checkout-root "$checkout_root"

checkout="$checkout_root/final-${sha:0:12}-${task}"
[[ ! -e $checkout ]] || { printf 'runner checkout already exists\n' >&2; exit 2; }
git -C "$repo_root" worktree add --detach "$checkout" "$sha"
cleanup_failed=0
marker="$checkout/.acceptance-runner-owner.json"
created_at=$(date --utc --iso-8601=seconds)
if ! (
  umask 077
  printf '{"lane":"final","sha":"%s","ref":"%s","task":"%s","creator":"acceptance-runner-v1","time":"%s"}\n' \
    "$sha" "$ref" "$task" "$created_at" > "$marker"
  chmod 0600 "$marker"
); then
  printf 'runner checkout marker creation failed; retaining checkout\n' >&2
  exit 1
fi

# The runner must return so its sealed evidence exists before checkout cleanup.
cd "$checkout"
export PYTHONPATH="$checkout/tools${PYTHONPATH:+:$PYTHONPATH}"
set +e
# Keep an exact task label in the runner process argv for cooperative recovery.
bash -c 'exec -a "$1" python3 -m acceptance.platform.runner "${@:2}"' \
  _ "--acceptance-task=$task" "${runner_args[@]}"
runner_status=$?
set -e

# Never remove a checkout while the wrapper's cwd still refers to it.
cd /
if ! python3 -c \
  'from pathlib import Path; from acceptance.platform.maintenance import validate_runner_checkout; import sys; validate_runner_checkout(Path(sys.argv[1]), Path(sys.argv[2]), lane=sys.argv[3], sha=sys.argv[4], ref=sys.argv[5], task=sys.argv[6])' \
  "$checkout_root" "$checkout" final "$sha" "$ref" "$task"; then
  printf 'runner checkout marker validation failed; retaining checkout\n' >&2
  cleanup_failed=1
elif [[ ! -f $marker || $(stat -c '%a' "$marker") != 600 ]]; then
  printf 'runner checkout marker validation failed; retaining checkout\n' >&2
  cleanup_failed=1
elif [[ $(git -C "$checkout" rev-parse HEAD) != "$sha" ]] \
  || git -C "$checkout" symbolic-ref -q HEAD >/dev/null 2>&1 \
  || [[ -n $(git -C "$checkout" status --porcelain=v1 --untracked-files=all -- . ':(exclude).acceptance-runner-owner.json') ]]; then
  printf 'runner checkout validation failed; retaining checkout\n' >&2
  cleanup_failed=1
else
  set +e
  git -C "$repo_root" worktree remove --force "$checkout"
  removal_status=$?
  set -e
  if ((removal_status != 0)) || [[ -e $checkout ]]; then
    printf 'runner checkout cleanup failed; sealed evidence retained\n' >&2
    cleanup_failed=1
  fi
fi

if ((cleanup_failed)); then
  exit 1
fi
exit "$runner_status"
