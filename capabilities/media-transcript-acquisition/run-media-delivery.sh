#!/usr/bin/env bash
set -euo pipefail
# Explicitly launched by user; no installation, service, or cron registration.
script_dir="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
  printf '%s\n' 'Python 3.11+ is required. See HOST_SETUP.md.' >&2
  exit 2
fi
exec python3 "$script_dir/host_app.py" "$@"
