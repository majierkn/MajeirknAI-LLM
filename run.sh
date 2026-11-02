#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
# -u mantem a saida sem buffer: as mensagens aparecem mesmo se o processo for
# encerrado por sinal (SIGTERM/SIGINT) antes de esvaziar o buffer.
exec python -u "$ROOT/main.py" "$@"
