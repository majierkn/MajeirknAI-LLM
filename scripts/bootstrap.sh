#!/data/data/com.termux/files/usr/bin/bash
# Instalacao por um unico comando, para amigos sem GitHub:
#
#   curl -fsSL <link>/bootstrap.sh | bash
#
# O script baixa o codigo do projeto, chama o install.sh e para antes do
# download do modelo (1,31 GB), que continua sendo opcao do usuario.
set -Eeuo pipefail

# Ajuste estes dois valores antes de distribuir o link.
REPO_URL="${MAJEIRKN_REPO_URL:-https://github.com/SEU-USUARIO/MajeirknAI-LLM/archive/refs/heads/main.tar.gz}"
RUNTIME_URL="${MAJEIRKN_RUNTIME_URL:-}"
TARGET="${MAJEIRKN_DIR:-$HOME/MajeirknAI-LLM}"
BRANCH_ZIP="${MAJEIRKN_BRANCH:-main}"

say() { printf '\n[majeirkn] %s\n' "$*"; }

if [[ -z "${PREFIX:-}" || ! -d "$PREFIX" ]]; then
  echo "Este instalador foi feito para o Termux. Abra o Termux e execute novamente."
  exit 1
fi

command -v curl >/dev/null 2>&1 || pkg install -y curl

say "baixando o projeto em $TARGET"
rm -rf "$TARGET"
mkdir -p "$TARGET"

if command -v git >/dev/null 2>&1 && [[ "$REPO_URL" == *.git ]]; then
  git clone --depth 1 "$REPO_URL" "$TARGET"
else
  # REPO_URL aponta para o tarball do codigo (ex.: codeload do GitHub).
  curl -fsSL "$REPO_URL" --output "$HOME/majeirkn-src.tar.gz"
  tar -xzf "$HOME/majeirkn-src.tar.gz" -C "$TARGET" --strip-components=1
  rm -f "$HOME/majeirkn-src.tar.gz"
fi

say "instalando o runtime"
MAJEIRKN_RUNTIME_URL="$RUNTIME_URL" bash "$TARGET/scripts/install.sh"

cat <<EOF

[majeirkn] Pronto. Falta so o modelo:

  bash $TARGET/scripts/download_model.sh     # ~1,31 GB, use Wi-Fi
  python $TARGET/main.py --web               # abre a interface no navegador

[majeirkn] Dica: para instalar como aplicativo, abra o endereco no Chrome e
use o menu > "Adicionar a tela inicial".
EOF
