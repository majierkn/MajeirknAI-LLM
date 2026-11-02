# Majeirkn AI para Android (APK)

Aplicativo que executa o mesmo modelo do projeto, sem o Termux: o `llama-server`
roda como processo filho dentro do app e a interface web abre em um WebView.

## Como funciona

```
MajeirknApp
  MainActivity  ->  WebView em http://127.0.0.1:8081
  LlamaService  ->  processo filho llama-server
                     (binarios copiados de assets para os arquivos do app)
```

- **Sem JNI e sem reescrever inferência**: os binários do llama.cpp são os
  mesmos usados no Termux, empacotados em `app/src/main/assets/arm64-v8a/`.
- A interface web é a **mesma** do projeto (`majeirkn/ui`), copiada para
  `app/src/main/assets/webui/`.
- O serviço cria os apelidos de biblioteca (`libX.so.0` -> `libX.so.0.28.0`)
  no diretório privado do app, onde o sistema aceita links simbólicos.

## Preparar os assets

No Termux, com o projeto compilado (`scripts/install_termux.sh`):

```bash
bash scripts/pack_apk_assets.sh
```

Isso copia os binários verificados e a interface web para `app/src/main/assets`.
O script falha se o `llama-server` não executar com o conjunto de arquivos.

## Buildar

Opção A — Android Studio: abra a pasta `android/` e rode o app.

Opção B — CI (recomendado, não precisa instalar o SDK): o workflow
`.github/workflows/apk.yml` builda o APK a cada push. Configure o segredo
`MAJEIRKN_RUNTIME_URL` do repositório com o link do tarball de runtime
(`scripts/pack_runtime.sh` gera o arquivo). O APK sai em *Artifacts*.

O APK gerado é de depuração (`assembleDebug`), já assinado e instalável. Para
publicar na Play Store, configure um keystore e use `assembleRelease`.

## O modelo

O APK **não inclui os pesos** (1,3 GB). No primeiro uso o app procura um
arquivo `.gguf` em `Download/`, `Download/modelos/`, `MajeirknAI/modelos/` e na
pasta interna; se não achar, pede para você escolher o arquivo. Use o mesmo
arquivo baixado pelo `scripts/download_model.sh`.

## Requisitos

- Android 8.0 (API 26) ou mais recente.
- Arquitetura `arm64-v8a` (praticamente todos os aparelhos atuais).
- Cerca de 3 GB de RAM livres: o modelo Q4_K_M ocupa 1,25 GB mais o cache.

## Limitações conhecidas

- O caminho do modelo é resolvido pelo SAF (`DocumentsContract`); URIs de
  provedores que não expõem caminho real (alguns apps de nuvem) não funcionam,
  porque o `llama-server` precisa de um caminho de arquivo.
- Compilar aqui no Termux **não é possível**: falta o SDK do Android. O build
  acontece no PC ou na CI.
- O APK ainda não foi testado em aparelho: a lógica é a mesma validada no
  Termux, mas o primeiro teste real deve ser feito por você.
