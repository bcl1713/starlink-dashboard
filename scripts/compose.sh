#!/bin/sh
# Bind ordinary Compose builds to the checked-out repository commit.
set -eu
repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if ! ACCEPTANCE_CANDIDATE_SHA=$(git -C "$repo_root" rev-parse --verify HEAD) ||
    ! printf '%s' "$ACCEPTANCE_CANDIDATE_SHA" | grep -Eq '^[0-9a-f]{40}$'; then
    printf '%s\n' 'Cannot determine a full checked-out HEAD SHA for Compose.' >&2
    exit 1
fi
export ACCEPTANCE_CANDIDATE_SHA
cd "$repo_root"
exec docker compose "$@"
