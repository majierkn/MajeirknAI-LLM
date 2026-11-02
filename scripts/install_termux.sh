#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LLAMA_DIR="$ROOT/vendor/llama.cpp"

if [[ -z "${PREFIX:-}" || ! -d "$PREFIX" ]]; then
  echo "Este instalador foi feito para Termux. Abra o Termux e execute novamente."
  exit 1
fi

pkg update -y
pkg install -y git cmake clang make pkg-config curl

mkdir -p "$ROOT/vendor"
if [[ ! -d "$LLAMA_DIR/.git" ]]; then
  git clone --depth 1 https://github.com/ggml-org/llama.cpp.git "$LLAMA_DIR"
else
  git -C "$LLAMA_DIR" pull --ff-only
fi

cmake -S "$LLAMA_DIR" -B "$LLAMA_DIR/build" \
  -DCMAKE_BUILD_TYPE=Release \
  -DGGML_NATIVE=ON \
  -DGGML_OPENMP=OFF \
  -DLLAMA_BUILD_TESTS=OFF \
  -DLLAMA_BUILD_EXAMPLES=ON

cmake --build "$LLAMA_DIR/build" --config Release -j2 --target llama-cli

echo
echo "Instalação concluída. Próximo passo: bash scripts/download_model.sh"
