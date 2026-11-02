#!/data/data/com.termux/files/usr/bin/bash
# Majeirkn AI - instalador de um comando.
#
#   curl -fsSL <link-deste-arquivo> | bash
#
# ANTES DE DISTRIBUIR, preencha as duas linhas abaixo:
#   REPO_URL     = de onde vem o codigo (tarball do GitHub ou repo .git)
#   RUNTIME_URL  = de onde vem o runtime pronto (release do GitHub, Drive etc.)
set -Eeuo pipefail

# ---------------------------------------------------------- PREENCHA AQUI
REPO_URL="${MAJEIRKN_REPO_URL:-https://github.com/SEU-USUARIO/MajeirknAI-LLM/archive/refs/heads/main.tar.gz}"
RUNTIME_URL="${MAJEIRKN_RUNTIME_URL:-https://github.com/SEU-USUARIO/MajeirknAI-LLM/releases/download/v0.2.0/majeirkn-runtime-aarch64-0.2.0.tar.gz}"
# -------------------------------------------------------- FIM DO PREENCHIDO

TARGET="${MAJEIRKN_DIR:-$HOME/MajeirknAI-LLM}"

say() { printf '\n[majeirkn] %s\n' "$*"; }

if [[ -z "${PREFIX:-}" || ! -d "$PREFIX" ]]; then
  echo "Este instalador foi feito para o Termux. Instale o Termux (F-Droid) e execute novamente."
  exit 1
fi

command -v curl >/dev/null 2>&1 || pkg install -y curl
command -v python >/dev/null 2>&1 || pkg install -y python

say "baixando o projeto em $TARGET"
rm -rf "$TARGET"
mkdir -p "$TARGET"
curl -fsSL "$REPO_URL" --output "$HOME/maja-src.tar.gz"
tar -xzf "$HOME/maja-src.tar.gz" -C "$TARGET" --strip-components=1
rm -f "$HOME/majeirkn-src.tar.gz"

say "instalando o runtime (sem compilar)"
MAJEIRKN_RUNTIME_URL="$RUNTIME_URL" bash "$TARGET/scripts/install.sh"

cat <<EOF

[majeirkn] Pronto. Falta apenas o modelo (1,31 GB, use Wi-Fi):

  bash $TARGET/scripts/download_model.sh
  python $TARGET/main.py --web

[majeirkn] Para instalar como aplicativo: abra o endereco no Chrome e use o
menu > "Adicionar a tela inicial".

[majeirkn] Precisa de Android 8+ com arquitetura arm64.
EOF
