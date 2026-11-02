#!/data/data/com.termux/files/usr/bin/bash
# Copia o runtime compilado e a interface web para dentro do projeto Android,
# em app/src/main/assets, de onde o APK os empacota.
#
#   android/app/src/main/assets/arm64-v8a/   binarios do llama.cpp
#   android/app/src/main/assets/webui/       interface web
#   android/app/src/main/assets/licenses/    licencas (MIT)
#
# A verificacao do binario acontece em $HOME: a pasta do projeto fica no
# armazenamento compartilhado, que nao guarda o bit de execucao (nem aceita
# symlinks). Dentro do APK isso nao importa - o servico copia os arquivos para
# a area privada do app e aplica setExecutable(true) la.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="${LLAMA_BUILD_DIR:-$HOME/majeirkn-build}"
BIN="$BUILD_DIR/bin"
ASSETS="$ROOT/android/app/src/main/assets"
STAGE="${MAJEIRKN_STAGE:-$HOME/.majeirkn-apk-pack}"

[[ -x "$BIN/llama-server" ]] || {
  echo "llama-server nao encontrado em $BIN"
  echo "Compile com: bash scripts/install_termux.sh"
  exit 1
}

# ---------------------------------------------------------------- 1. staging
# So os arquivos reais + os executivos (~23 MB). Os nomes alternativos
# (libX.so.0) sao criados em runtime pelo servico Android no diretorio privado
# do app, que aceita symlinks; copiar cada alias duplicaria o tamanho do APK.
REAL_FILES=(
  llama-server
  llama-cli
  libllama-server-impl.so
  libllama-cli-impl.so
  libggml-base.so.0.28.0
  libggml-cpu.so.0.28.0
  libggml.so.0.28.0
  libllama-common.so.0.8.0
  libllama.so.0.8.0
  libmtmd.so.0.8.0
)

rm -rf "$STAGE"
mkdir -p "$STAGE/arm64-v8a"

for name in "${REAL_FILES[@]}"; do
  [[ -e "$BIN/$name" ]] || { echo "arquivo ausente no build: $name"; exit 1; }
  cp -a "$BIN/$name" "$STAGE/arm64-v8a/$name"
done
chmod +x "$STAGE/arm64-v8a/llama-server" "$STAGE/arm64-v8a/llama-cli"

# Recria os aliases para validar o conjunto exato que vai no APK.
ln -sf libggml-base.so.0.28.0 "$STAGE/arm64-v8a/libggml-base.so.0"
ln -sf libggml-cpu.so.0.28.0 "$STAGE/arm64-v8a/libggml-cpu.so.0"
ln -sf libggml.so.0.28.0 "$STAGE/arm64-v8a/libggml.so.0"
ln -sf libllama-common.so.0.8.0 "$STAGE/arm64-v8a/libllama-common.so.0"
ln -sf libllama.so.0.8.0 "$STAGE/arm64-v8a/libllama.so.0"
ln -sf libmtmd.so.0.8.0 "$STAGE/arm64-v8a/libmtmd.so.0"

# Verifica de verdade: carrega as libs do proprio conjunto.
echo "verificando os binarios..."
if ! LD_LIBRARY_PATH="$STAGE/arm64-v8a" "$STAGE/arm64-v8a/llama-server" --version >/dev/null 2>&1; then
  echo "FALHA: o llama-server nao executa com os arquivos do pacote."
  exit 1
fi

# ------------------------------------------------------------- 2. no projeto
rm -rf "$ASSETS/arm64-v8a" "$ASSETS/webui" "$ASSETS/licenses"
mkdir -p "$ASSETS/arm64-v8a" "$ASSETS/webui" "$ASSETS/licenses"

# So arquivos regulares: os aliases do staging sao apenas para a verificacao
# local e precisam ficar de fora (o APK os recria em runtime).
find "$STAGE/arm64-v8a" -maxdepth 1 -type f -exec cp -rL {} "$ASSETS/arm64-v8a/" \;

cp -a "$ROOT/majeirkn/ui/." "$ASSETS/webui/"
cp -a "$ROOT/LICENSE" "$ASSETS/licenses/majeirkn-MIT.txt"
cp -a "$ROOT/vendor/llama.cpp/LICENSE" "$ASSETS/licenses/llama.cpp-MIT.txt" 2>/dev/null || true

echo "Assets do APK atualizados em $ASSETS"
du -sh "$ASSETS/arm64-v8a" "$ASSETS/webui" "$ASSETS/licenses"
