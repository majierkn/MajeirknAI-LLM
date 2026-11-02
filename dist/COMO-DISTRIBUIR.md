# Como distribuir a Majeirkn AI para os amigos

Tudo que esta nesta pasta `dist/` vai para o **mesmo lugar** (uma pasta do
Google Drive ou Dropbox com link publico, ou os assets de uma release do
GitHub). Nada precisa ser renomerado.

## O que existe aqui

| Arquivo | Para que |
|---|---|
| `majeirkn-runtime-aarch64-0.2.0.tar.gz` | binarios do llama.cpp (9,5 MB) |
| `majeirkn-runtime-aarch64-0.2.0.tar.gz.sha256` | verificacao de integridade |
| `bootstrap.sh` | instalador de um comando para o amigo |

## Passo a passo

1. **Crie o repositorio no GitHub** (privado, como voce decidiu) e suba o codigo:
   ```bash
   git remote add origin https://github.com/SEU-USUARIO/MajeirknAI-LLM.git
   git push -u origin main
   ```

2. **Crie uma release** chamada `v0.2.0` (Releases > Draft a new release) e
   suba nela os dois arquivos do runtime: o `.tar.gz` e o `.sha256`. Depois de
   publicar, use o link direto do asset (botao direito > copiar link) no
   proximo passo.

3. **Preencha os dois links no `bootstrap.sh`** desta pasta:
   - `REPO_URL`: endereco do codigo. Sem git para o amigo, use o tarball do
     proprio GitHub:
     `https://github.com/SEU-USUARIO/MajeirknAI-LLM/archive/refs/heads/main.tar.gz`
   - `RUNTIME_URL`: link direto do asset da release (ou de onde voce subiu o
     tarball, se nao for usar o GitHub).

4. **Suba a pasta `dist/` inteira** para o Drive/Dropbox e compartilhe o link.

5. **Teste antes de espalhar**: em um Termux limpo (ou peça a um amigo), rode
   `curl -fsSL <link-do-bootstrap>/bootstrap.sh | bash`. Ele deve instalar o
   runtime sem compilar e parar antes do download do modelo.

## O que o amigo recebe

So o link do `bootstrap.sh`. A mensagem pronta esta no LEIA-ME do projeto.

## Observacoes honestas

- O `install.sh` foi testado com o tarball em caminho local (`file://`), nao com
  URL de HTTP real. A logica e a mesma, mas vale o teste do passo 5.
- O APK so foi preparado como projeto; ninguem ainda buildou ele em aparelho
  real. O caminho testado de ponta a ponta e o Termux (`main.py --web`).
