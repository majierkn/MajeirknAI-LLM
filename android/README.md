# Majeirkn AI para Android (APK ARM64)

O aplicativo executa llama-server como processo filho e abre a interface web local em http://127.0.0.1:8081.

## Runtime Snapdragon ARM64

O pacote de runtime fornecido tem a estrutura:

~~~text
llama.cpp/
  bin/libllama-server.so
  lib/libllama-server-impl.so
  lib/libllama-common.so
  lib/libmtmd.so
  lib/libllama.so
  lib/libggml.so
  lib/libggml-cpu.so
  lib/libggml-opencl.so
  lib/libggml-hexagon.so
  lib/libggml-base.so
  lib/libggml-htp-v*.so   # blobs Qualcomm DSP6, nao ELF ARM64
~~~

O executável PIE do servidor é instalado em app/src/main/jniLibs/arm64-v8a/libllama-server.so. Com extractNativeLibs=true, o Android extrai esse arquivo em ApplicationInfo.nativeLibraryDir, onde o serviço o inicia. Isso evita executar o binário diretamente em filesDir e corrige o caminho associado ao erro 13.

As bibliotecas e os blobs Qualcomm são copiados dos assets para filesDir/bin. Os SONAMEs do pacote são nomes sem versão, como libllama.so e libggml.so. O serviço também mantém compatibilidade com arquivos versionados de runtimes antigos.

**Compatibilidade:** este runtime é direcionado a aparelhos Snapdragon compatíveis. libggml-opencl.so depende de libOpenCL.so, que precisa ser fornecida e estar acessível pelo driver Qualcomm do aparelho. Os arquivos libggml-htp-v*.so são blobs Qualcomm DSP6 e não bibliotecas ELF ARM64 comuns; são mantidos como arquivos de dados para o backend Hexagon.

O runtime recebido não declara dependência de libssl.so.3 nem libcrypto.so.3, então o build não exige esses arquivos. libc++_shared.so também não é adicionada sem dependência ELF explícita.

## Preparar assets manualmente

Em Termux/Linux com tar e binutils instalados:

~~~bash
MAJEIRKN_RUNTIME_ARCHIVE=/caminho/llama-cpp-snapdragon.tar.gz bash scripts/pack_apk_assets.sh
~~~

## Gerar o APK pelo GitHub Actions

1. Publique o arquivo .tar.gz do runtime em um GitHub Release ou outro local que ofereça uma URL direta de download.
2. Abra Actions > APK Android ARM64 > Run workflow.
3. Cole a URL direta no campo runtime_url. Alternativamente, configure o segredo MAJEIRKN_RUNTIME_URL com a mesma URL.
4. Quando o processo terminar, baixe o artefato majeirkn-apk-arm64 e instale o APK de depuração.

O workflow valida as bibliotecas AArch64, copia a interface web, compila com Gradle e publica o APK como artefato. A compilação não substitui o teste em um aparelho Snapdragon real: disponibilidade de libOpenCL.so, suporte do backend Hexagon e compatibilidade do modelo precisam ser verificados no dispositivo.

## Modelo e limitações

O APK não inclui os pesos GGUF. No primeiro uso, selecione um arquivo .gguf local. O modelo precisa caber na memória RAM disponível.

- Android 8.0 (API 26) ou mais recente; ABI arm64-v8a.
- Aparelho Snapdragon compatível com os drivers exigidos pelo runtime.
- O provedor de documentos precisa permitir acesso a um caminho local que o servidor consiga abrir.
- O APK gerado pelo workflow é de depuração e ainda precisa de teste no aparelho antes de distribuição.
