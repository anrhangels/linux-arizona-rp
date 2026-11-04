#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
    printf 'Нужен Python 3.10 или новее.\n' >&2
    exit 1
fi
if (( $# == 0 )); then
    exec python3 "$script_dir/arizona.py" launch
fi
exec python3 "$script_dir/arizona.py" "$@"
