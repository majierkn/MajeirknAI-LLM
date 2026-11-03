# Majeirkn AI para Android (ARM64 CPU)

O aplicativo executa `llama-server` como processo filho e abre a interface web local em `http://127.0.0.1:8081`.

## Compatibilidade do dispositivo

O build fornecido pelo workflow é um runtime Android `arm64-v8a` portável, com backend CPU e KleidiAI opcional. Ele não usa OpenCL, Hexagon, HTP nem bibliotecas exclusivas de Snapdragon. Isso permite gerar um APK para aparelhos ARM64 com diferentes fabricantes de SoC, incluindo dispositivos MediaTek, desde que tenham memória suficiente para o modelo escolhido.

O Samsung Galaxy M53 5G (SM-M536B) usa MediaTek Dimensity 900; por isso, o pacote Snapdragon/Qualcomm enviado anteriormente não é usado neste build. O novo runtime é compilado a partir do código oficial do llama.cpp com Android NDK, para CPU ARM64 genérica.

## Como o runtime é compilado

O workflow usa Android NDK e CMake com as opções recomendadas pelo projeto oficial llama.cpp para Android:

- ABI `arm64-v8a` e plataforma Android 28 (API 28).
- `GGML_NATIVE=OFF`, necessário em compilação cruzada.
- `GGML_OPENMP=OFF` e `GGML_LLAMAFILE=OFF` para evitar dependências não suportadas nessa configuração.
- `LLAMA_OPENSSL=OFF`, porque OpenSSL não faz parte da API nativa estável do Android NDK.
- `GGML_CPU_KLEIDIAI=ON`, com seleção de kernels compatíveis em tempo de execução.

O executável PIE é instalado em `app/src/main/jniLibs/arm64-v8a/libllama-server.so`. Com `extractNativeLibs=true`, o Android extrai o arquivo em `ApplicationInfo.nativeLibraryDir`, onde o serviço o inicia. Isso evita o erro 13 associado à execução de binários copiados para `filesDir`.

Bibliotecas compartilhadas, se existirem no prefixo de instalação, ficam em `app/src/main/assets/arm64-v8a/` e são copiadas para `filesDir/bin`. O serviço mantém compatibilidade com SONAMEs versionados de builds antigos e ignora aliases quando o arquivo de destino não existe.

## Gerar o APK no GitHub

1. Abra o repositório `majierkn/MajeirknAI-LLM` no GitHub.
2. Entre na aba **Actions**.
3. Selecione **APK Android ARM64 (CPU)**.
4. Clique em **Run workflow** e confirme.
5. Quando terminar com sucesso, abra a execução e baixe o artefato `majeirkn-apk-arm64-cpu`.

Não é necessário enviar o runtime Snapdragon, configurar uma URL de tarball ou criar o segredo `MAJEIRKN_RUNTIME_URL`: o GitHub Actions compila o llama.cpp para Android ARM64 durante o build.

## Modelo de IA

O APK não inclui pesos GGUF. No primeiro uso, selecione um arquivo `.gguf` acessível ao aplicativo. O tamanho do modelo, quantização, contexto e memória livre determinam se ele consegue carregar e responder. Comece com um modelo pequeno e quantizado.

## Requisitos e observações

- Android 9 (API 28) ou mais recente.
- ABI `arm64-v8a`.
- Espaço livre para o APK, modelo e cache; RAM suficiente para o modelo.
- Build de depuração assinado com a chave de debug do Gradle; não é uma versão assinada para publicação na Play Store.
- Uma execução verde no GitHub Actions comprova a compilação, mas ainda é necessário instalar e testar o APK em um aparelho real. O desempenho varia conforme CPU, RAM, temperatura e tamanho do GGUF.

## Preparação manual dos assets

Depois de compilar e instalar o llama.cpp com Android NDK, é possível preparar os assets localmente:

```bash
LLAMA_INSTALL_DIR=/caminho/para/install bash scripts/pack_apk_assets.sh
```
