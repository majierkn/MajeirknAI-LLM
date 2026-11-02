#!/data/data/com.termux/files/usr/bin/bash
# Instalacao rapida da Majeirkn AI no Termux: baixa o runtime pre-compilado
# (llama-server + bibliotecas) em vez de compilar no aparelho.
#
# Se o binario pronto nao servir (outra arquitetura ou incompatibilidade de
# bibliotecas), o script cai automaticamente no install_termux.sh, que compila.
#
# Variaveis uteis:
#   MAJEIRKN_RUNTIME_URL   link direto do tarball (padrao: vazio = compilar)
#   LLAMA_BUILD_DIR        onde ficam os binarios (padrao: $HOME/majeirkn-build)
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="${LLAMA_BUILD_DIR:-$HOME/majeirkn-build}"
RUNTIME_URL="${MAJEIRKN_RUNTIME_URL:-}"
ARCH="$(uname -m)"
VERSION="$(python3 -c 'import sys; sys.path.insert(0, "."); from majeirkn import __version__; print(__version__)' 2>/dev/null || echo dev)"

say() { printf '\n[majeirkn] %s\n' "$*"; }

if [[ -z "${PREFIX:-}" || ! -d "$PREFIX" ]]; then
  echo "Este instalador foi feito para o Termux. Abra o Termux e execute novamente."
  exit 1
fi

say "arquitetura: $ARCH  versao: $VERSION"

# Dependencias minimas: OpenSSL (libssl/libcrypto), libc++ e o Python.
say "instalando dependencias do Termux"
pkg install -y openssl libc++ python

have_binary() {
  [[ -x "$BUILD_DIR/bin/llama-server" ]] && "$BUILD_DIR/bin/llama-server" --version >/dev/null 2>&1
}

if [[ -n "$RUNTIME_URL" ]]; then
  say "baixando runtime pre-compilado"
  TMP_TAR="$HOME/majeirkn-runtime-$ARCH.tar.gz"
  SAVE_PATH="$TMP_TAR"

  if curl --fail --location --retry 3 --retry-delay 3 --continue-at - \
      "$RUNTIME_URL" --output "$TMP_TAR"; then
    mkdir -p "$BUILD_DIR/bin"
    if tar -xzf "$TMP_TAR" -C "$BUILD_DIR" --strip-components=1 runtime/bin; then
      chmod +x "$BUILD_DIR/bin/llama-server" "$BUILD_DIR/bin/llama-cli" 2>/dev/null || true
      rm -f "$TMP_TAR"
      if have_binary; then
        say "llama-server instalado em $BUILD_DIR/bin (sem compilar)"
        "$BUILD_DIR/bin/llama-server" --version | head -2
        exit 0
      fi
      say "o binario baixado nao executa neste aparelho; compilando do fonte"
    else
      say "tarball inesperado; compilando do fonte"
    fi
  else
    say "download falhou; compilando do fonte"
  fi
else
  say "MAJEIRKN_RUNTIME_URL nao definido; compilando do fonte (~30-60 min no celular)"
fi

bash "$ROOT/scripts/install_termux.sh"
