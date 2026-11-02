#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
exec python "$ROOT/main.py" "$@"
