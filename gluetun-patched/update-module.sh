#!/usr/bin/env bash
# Generate a reviewed module update against the exact source, never a manifest-only
# directory. Does not build/deploy the VPN candidate or touch production credentials.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
if [ "$#" -ne 2 ] || [[ ! "$1" =~ ^[a-zA-Z0-9][a-zA-Z0-9./_-]+$ ]] || [[ ! "$2" =~ ^v[0-9][a-zA-Z0-9.+_-]*$ ]]; then
  echo 'Usage: update-module.sh module/path vX.Y.Z' >&2
  exit 2
fi
module=$1 version=$2
task_tmp=$(mktemp -d)
container="pb-module-update-$(basename "$task_tmp" | tr '[:upper:].' '[:lower:]-')"
cleanup() { docker rm -f "$container" >/dev/null 2>&1 || true; rm -rf "$task_tmp"; }
trap cleanup EXIT
# Refuse to overwrite an edit made while source resolution is running.
cp go.mod "$task_tmp/original.mod"
cp go.sum "$task_tmp/original.sum"
# Use the immutable stage ID rather than a shared mutable helper tag.
source_image=$(docker build --quiet --target source .)
docker create --name "$container" "$source_image" \
  sh -ec 'go get "$1@$2"; go mod tidy; go mod verify; test "$(go list -m -f "{{.Version}}" "$1")" = "$2"' -- "$module" "$version" >/dev/null
docker start -a "$container"
# docker start may report transport success even when the command failed.
[ "$(docker inspect -f '{{.State.ExitCode}}' "$container")" = 0 ] || exit 1
docker cp "$container:/src/go.mod" "$task_tmp/go.mod"
docker cp "$container:/src/go.sum" "$task_tmp/go.sum"
# Keep original files if retrieval fails; review generated graph before committing.
[ -s "$task_tmp/go.mod" ] && [ -s "$task_tmp/go.sum" ]
if ! cmp -s go.mod "$task_tmp/original.mod" || ! cmp -s go.sum "$task_tmp/original.sum"; then
  echo "Module files changed during generation; refusing overwrite" >&2
  exit 1
fi
cp "$task_tmp/go.mod" go.mod
cp "$task_tmp/go.sum" go.sum
printf '%s\n' 'Module graph generated. Review the diff, then build/test/scan and validate the candidate before merge or deployment.'
