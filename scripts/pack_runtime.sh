#!/data/data/com.termux/files/usr/bin/bash
# Empacota o runtime pre-compilado (llama-server + bibliotecas) para distribuir
# aos amigos sem que eles precisem compilar nada.
#
# Saida: dist/majeirkn-runtime-<arquitetura>-<versao>.tar.gz + .sha256
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BUILD_DIR="${LLAMA_BUILD_DIR:-$HOME/majeirkn-build}"
BIN="$BUILD_DIR/bin"
OUT="$ROOT/dist"
VERSION="$(python3 -c 'import sys; sys.path.insert(0, "."); from majeirkn import __version__; print(__version__)')"
ARCH="$(uname -m)"

[[ -x "$BIN/llama-server" ]] || {
  echo "llama-server nao encontrado em $BIN"
  echo "Compile com: bash scripts/install_termux.sh"
  exit 1
}

STAGE="${MAJEIRKN_STAGE:-$HOME/.majeirkn-pack}/runtime"
rm -rf "${MAJEIRKN_STAGE:-$HOME/.majeirkn-pack}"
mkdir -p "$STAGE/bin" "$STAGE/licenses" "$OUT"
# A montagem fica no $HOME: /storage/emulated/0 nao aceita links simbolicos e
# as bibliotecas .so sao links (libX.so -> libX.so.0 -> libX.so.0.28.0).

# Copia tudo do bin/: alem dos executivos, as bibliotecas de verdade
# (libX.so.0.28.0) e os links simbolicos que apontam para elas. Um glob apenas
# por *.so pegaria so os links e geraria um pacote que nao carrega.
cp -a "$BIN"/. "$STAGE/bin"/

# Dependencias do Termux que o Android nao fornece (o app Android as exige).
for name in libssl.so.3 libcrypto.so.3 libc++_shared.so; do
  if [[ ! -e "$STAGE/bin/$name" ]]; then
    cp -aL "${PREFIX:-/data/data/com.termux/files/usr}/lib/$name" "$STAGE/bin/$name" || {
      echo "dependencia ausente: $name (instale com: pkg install openssl libc++)"
      exit 1
    }
  fi
done

# Auto-verificacao: roda o binario empacotado com as libs do proprio pacote.
# Sem isso, um pacote com link quebrado passaria despercebido.
echo "verificando o pacote..."
if ! LD_LIBRARY_PATH="$STAGE/bin" "$STAGE/bin/llama-server" --version >/dev/null 2>&1; then
  echo "FALHA: o llama-server empacotado nao executa com as bibliotecas do pacote."
  echo "Os links simbolicos provavelmente ficaram sem os arquivos reais."
  exit 1
fi

# Licencas: o projeto e MIT e o runtime e do llama.cpp (MIT).
cp -a "$ROOT/LICENSE" "$STAGE/licenses/majeirkn-MIT.txt"
cp -a "$ROOT/vendor/llama.cpp/LICENSE" "$STAGE/licenses/llama.cpp-MIT.txt" 2>/dev/null || true
cp -a "$ROOT/vendor/llama.cpp/README.md" "$STAGE/licenses/llama.cpp-README.md" 2>/dev/null || true

# Rastreabilidade: commit do vendor e data do empacotamento. O vendor pode ser
# de outro usuario (git "dubious ownership"), por isso safe.directory inline.
LLAMA_COMMIT="(vendor sem .git)"
if [[ -d "$ROOT/vendor/llama.cpp/.git" ]]; then
  LLAMA_COMMIT="$(git -c safe.directory="*" -C "$ROOT/vendor/llama.cpp" \
    rev-parse --short HEAD 2>/dev/null || echo desconhecido)"
fi

{
  echo "majeirkn $VERSION"
  echo "arquitetura $ARCH"
  echo "empacotado $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
  echo "llama.cpp $LLAMA_COMMIT"
} > "$STAGE/VERSION.txt"

TARBALL="$OUT/majeirkn-runtime-$ARCH-$VERSION.tar.gz"
STAGE_ROOT="$(dirname "$STAGE")"
tar -czf "$TARBALL" -C "$STAGE_ROOT" runtime
sha256sum "$TARBALL" > "$TARBALL.sha256"

echo "Pacote criado:"
echo "  $TARBALL ($(du -h "$TARBALL" | cut -f1))"
echo "  $TARBALL.sha256"
echo
echo "Suba os dois arquivos no mesmo lugar (GitHub Release, Drive ou Dropbox)."
