#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$(readlink -f -- "$0")")"
if ! command -v python3 >/dev/null 2>&1; then
  echo 'Python 3.10 or newer is required. See QUICKSTART.md for installation help.' >&2
  exit 2
fi
exec python3 scripts/onboard.py "$@"
