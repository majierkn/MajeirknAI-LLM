#!/usr/bin/env bash
# Prepara o APK usando o runtime Android ARM64 fornecido em .tar.gz.
# Uso: MAJEIRKN_RUNTIME_ARCHIVE=/caminho/runtime.tar.gz bash scripts/pack_apk_assets.sh
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ARCHIVE="${MAJEIRKN_RUNTIME_ARCHIVE:-}"
if [[ -z "$ARCHIVE" || ! -s "$ARCHIVE" ]]; then
  echo "Informe MAJEIRKN_RUNTIME_ARCHIVE com o caminho do .tar.gz Android ARM64."
  exit 2
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/unpacked"
tar -xzf "$ARCHIVE" -C "$WORK/unpacked"
RUNTIME="$WORK/unpacked/llama.cpp"
SERVER="$RUNTIME/bin/libllama-server.so"
LIBDIR="$RUNTIME/lib"
[[ -s "$SERVER" && -d "$LIBDIR" ]] || {
  echo "Runtime invalido: esperado llama.cpp/bin/libllama-server.so e llama.cpp/lib/*.so"
  exit 1
}

command -v readelf >/dev/null 2>&1 || {
  echo "Instale binutils para validar o ELF (Termux: pkg install binutils)."
  exit 1
}
readelf -h "$SERVER" | grep -q 'Machine:.*AArch64' || {
  echo "O executavel nao e ARM64/AArch64."; exit 1;
}

ASSETS="$ROOT/android/app/src/main/assets"
JNI="$ROOT/android/app/src/main/jniLibs/arm64-v8a"
rm -rf "$ASSETS/arm64-v8a" "$JNI"
mkdir -p "$ASSETS/arm64-v8a" "$ASSETS/webui" "$ASSETS/licenses" "$JNI"
find "$LIBDIR" -maxdepth 1 -type f -name '*.so' -exec cp -L {} "$ASSETS/arm64-v8a/" \;

REQUIRED_LIBS=(
  libllama-server-impl.so
  libllama-common.so
  libmtmd.so
  libllama.so
  libggml.so
  libggml-cpu.so
  libggml-opencl.so
  libggml-hexagon.so
  libggml-base.so
)
for lib in "${REQUIRED_LIBS[@]}"; do
  [[ -s "$ASSETS/arm64-v8a/$lib" ]] || { echo "Biblioteca ausente: $lib"; exit 1; }
  readelf -h "$ASSETS/arm64-v8a/$lib" | grep -q 'Machine:.*AArch64' || {
    echo "$lib nao e ELF ARM64."; exit 1;
  }
done

# O executavel PIE fica em jniLibs para o Android extraí-lo com permissao de
# execucao. Nunca execute o binario diretamente de filesDir/assets.
install -m 0755 "$SERVER" "$JNI/libllama-server.so"
rm -rf "$ASSETS/webui" "$ASSETS/licenses"
mkdir -p "$ASSETS/webui" "$ASSETS/licenses"
cp -a "$ROOT/majeirkn/ui/." "$ASSETS/webui/"
cp "$ROOT/LICENSE" "$ASSETS/licenses/majeirkn-MIT.txt"
if [[ -f "$ROOT/vendor/llama.cpp/LICENSE" ]]; then
  cp "$ROOT/vendor/llama.cpp/LICENSE" "$ASSETS/licenses/llama.cpp-MIT.txt"
fi

echo "Assets Android ARM64 preparados."
echo "Servidor: $JNI/libllama-server.so"
echo "Bibliotecas: $ASSETS/arm64-v8a/"
echo "Aviso: libOpenCL.so precisa estar acessivel pelo driver Qualcomm do aparelho."
