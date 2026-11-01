#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODEL_DIR="$ROOT/models"
MODEL_FILE="$MODEL_DIR/Qwen3.5-2B-Q4_K_M.gguf"
MODEL_URL="https://huggingface.co/SoAIHQ/Qwen3.5-2B-GGUF/resolve/main/Qwen3.5-2B-Q4_K_M.gguf"

mkdir -p "$MODEL_DIR"
if [[ -s "$MODEL_FILE" ]]; then
  echo "O arquivo do modelo já existe: $MODEL_FILE"
  echo "Apague-o manualmente para baixar novamente."
  exit 0
fi

command -v curl >/dev/null 2>&1 || {
  echo "curl não encontrado. Instale com: pkg install curl"
  exit 1
}

echo "Baixando Qwen3.5-2B Q4_K_M (aprox. 1,31 GB)."
echo "Use Wi-Fi e mantenha espaço livre suficiente no armazenamento."
curl --fail --location --retry 5 --retry-delay 3 --continue-at - \
  "$MODEL_URL" --output "$MODEL_FILE"

if [[ ! -s "$MODEL_FILE" ]]; then
  echo "Download incompleto. Execute este script novamente para continuar."
  exit 1
fi

echo "Download concluído: $MODEL_FILE"
