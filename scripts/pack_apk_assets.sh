#!/usr/bin/env bash
# Empacota um llama.cpp Android arm64-v8a ja compilado pelo NDK.
# Uso: LLAMA_INSTALL_DIR=/caminho/install bash scripts/pack_apk_assets.sh
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL_DIR="${LLAMA_INSTALL_DIR:-}"
if [[ -z "$INSTALL_DIR" || ! -d "$INSTALL_DIR" ]]; then
  echo "Informe LLAMA_INSTALL_DIR apontando para o prefixo de cmake --install."
  exit 2
fi
SERVER="$INSTALL_DIR/bin/llama-server"
if [[ ! -s "$SERVER" ]]; then
  echo "Executavel ausente: $SERVER"
  exit 1
fi
command -v readelf >/dev/null 2>&1 || {
  echo "Instale binutils para validar o executavel (Termux: pkg install binutils)."
  exit 1
}
readelf -h "$SERVER" | grep -q 'Machine:.*AArch64' || {
  echo "llama-server nao e ELF ARM64/AArch64."; exit 1;
}

ASSETS="$ROOT/android/app/src/main/assets"
JNI="$ROOT/android/app/src/main/jniLibs/arm64-v8a"
rm -rf "$ASSETS/arm64-v8a" "$JNI"
mkdir -p "$ASSETS/arm64-v8a" "$ASSETS/webui" "$ASSETS/licenses" "$JNI"
for libdir in "$INSTALL_DIR/lib" "$INSTALL_DIR/lib64"; do
  if [[ -d "$libdir" ]]; then
    find "$libdir" -maxdepth 1 -type f -name '*.so*' -exec cp -L {} "$ASSETS/arm64-v8a/" \\;
  fi
done
for lib in "$ASSETS/arm64-v8a"/*.so*; do
  [[ -e "$lib" ]] || continue
  readelf -h "$lib" | grep -q 'Machine:.*AArch64' || {
    echo "Biblioteca nao e ELF ARM64: $lib"; exit 1;
  }
done
if readelf -d "$SERVER" | grep -Eiq 'lib(OpenCL|ssl|crypto|ggml-hexagon|ggml-htp)'; then
  echo "O servidor nao parece ser um build CPU portatil: detectada dependencia OpenCL/OpenSSL/Qualcomm."
  exit 1
fi
install -m 0755 "$SERVER" "$JNI/libllama-server.so"
rm -rf "$ASSETS/webui" "$ASSETS/licenses"
mkdir -p "$ASSETS/webui" "$ASSETS/licenses"
cp -a "$ROOT/majeirkn/ui/." "$ASSETS/webui/"
cp "$ROOT/LICENSE" "$ASSETS/licenses/majeirkn-MIT.txt"
if [[ -f "$ROOT/vendor/llama.cpp/LICENSE" ]]; then
  cp "$ROOT/vendor/llama.cpp/LICENSE" "$ASSETS/licenses/llama.cpp-MIT.txt"
fi

echo "Assets Android ARM64 CPU preparados."
echo "Servidor: $JNI/libllama-server.so"
echo "Bibliotecas: $ASSETS/arm64-v8a/"
echo "Dependencias NEEDED:"
readelf -d "$JNI/libllama-server.so" | grep NEEDED || true
