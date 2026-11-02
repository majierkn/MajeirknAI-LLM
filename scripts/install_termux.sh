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
# safe.directory="*": o vendor pode ter vindo de outro usuario (ex.: copiado
# do armazenamento compartilhado) e o git recusaria com "dubious ownership".
if [[ ! -d "$LLAMA_DIR/.git" ]]; then
  git clone --depth 1 https://github.com/ggml-org/llama.cpp.git "$LLAMA_DIR"
else
  git -c safe.directory="*" -C "$LLAMA_DIR" pull --ff-only
fi

# O build fica no armazenamento privado do Termux ($HOME): /storage/emulated/0
# não permite links simbólicos e a compilação falharia com "Permission denied".
BUILD_DIR="${LLAMA_BUILD_DIR:-$HOME/majeirkn-build}"

cmake -S "$LLAMA_DIR" -B "$BUILD_DIR" \
  -DCMAKE_BUILD_TYPE=Release \
  -DGGML_NATIVE=ON \
  -DGGML_OPENMP=OFF \
  -DLLAMA_BUILD_TESTS=OFF \
  -DLLAMA_BUILD_EXAMPLES=ON

# llama-server serve a interface web e a API HTTP; llama-cli e o terminal puro.
cmake --build "$BUILD_DIR" --config Release -j2 --target llama-server llama-cli

if [[ ! -x "$BUILD_DIR/bin/llama-server" ]]; then
  echo "Falha ao compilar llama-server. Verifique a saída acima."
  exit 1
fi
if [[ ! -x "$BUILD_DIR/bin/llama-cli" ]]; then
  echo "Falha ao compilar llama-cli. Verifique a saída acima."
  exit 1
fi
echo "llama-server compilado em: $BUILD_DIR/bin/llama-server"
echo "llama-cli compilado em: $BUILD_DIR/bin/llama-cli"

echo
echo "Instalação concluída. Próximo passo: bash scripts/download_model.sh"
