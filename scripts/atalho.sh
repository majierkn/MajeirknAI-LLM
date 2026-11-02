#!/data/data/com.termux/files/usr/bin/bash
# Atalho de um toque para a Majeirkn AI na interface web.
#
# Instalacao:
#   mkdir -p ~/.shortcuts/tasks
#   cp scripts/atalho.sh ~/.shortcuts/tasks/MajeirknAI.sh
#   chmod +x ~/.shortcuts/tasks/MajeirknAI.sh
# Depois adicione o widget "Termux:Widget" na tela inicial e escolha
# "MajeirknAI.sh". Um toque liga o servidor e (se o termux-api estiver
# instalado) abre o navegador.
set -Eeuo pipefail

# Quando copiado para ~/.shortcuts/tasks, $0 nao sabe onde esta o projeto:
# usa MAJEIRKN_ROOT, depois o caminho padrao, e por ultimo o repo local.
ROOT="${MAJEIRKN_ROOT:-$HOME/MajeirknAI-LLM}"
if [[ ! -f "$ROOT/main.py" ]]; then
  ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fi
cd "$ROOT"

# Encerra um servidor antigo para nao conflitar na porta (padrao 8081).
pkill -f 'llama[-]server' 2>/dev/null || true
sleep 1

exec python -u main.py --web
