#!/usr/bin/env bash
set -euo pipefail
# User-launched only. Never installs packages, changes system Python or schedules work.
script_dir="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
supports_python() {
  command -v "$1" >/dev/null 2>&1 && "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1
}
if [[ -n "${AUTOMATION_PYTHON:-}" ]]; then
  if supports_python "$AUTOMATION_PYTHON"; then
    exec "$AUTOMATION_PYTHON" "$script_dir/host_app.py" "$@"
  fi
  printf '%s\n' 'AUTOMATION_PYTHON is not an accessible Python 3.11+ interpreter.' >&2
  exit 2
fi
for interpreter in python3 python3.15 python3.14 python3.13 python3.12 python3.11; do
  if supports_python "$interpreter"; then
    exec "$interpreter" "$script_dir/host_app.py" "$@"
  fi
done
printf '%s\n' 'Python 3.11+ was not found. See HOST_SETUP.md; leave system Python unchanged.' >&2
exit 2
