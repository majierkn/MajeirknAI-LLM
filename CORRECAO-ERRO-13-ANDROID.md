# Correção do erro 13 e build ARM64 portável para Android

O erro `error=13: Permission denied` ocorria porque o aplicativo tentava executar o servidor llama.cpp a partir de um diretório privado gravável (`files/bin`). O Android pode bloquear a execução de arquivos nesse local.

## Correção do lançamento

- O executável `llama-server` é compilado para Android `arm64-v8a`.
- Ele é empacotado como `android/app/src/main/jniLibs/arm64-v8a/libllama-server.so`.
- Com `android:extractNativeLibs="true"`, o Android extrai o binário em `ApplicationInfo.nativeLibraryDir`.
- O serviço inicia o executável diretamente desse diretório, em vez de iniciar um arquivo dentro de `filesDir`.
- As bibliotecas compartilhadas necessárias são copiadas de `assets/arm64-v8a` para `files/bin`, e `LD_LIBRARY_PATH` é configurado no processo.

## Compatibilidade do runtime

O runtime Snapdragon fornecido anteriormente contém componentes Qualcomm OpenCL/Hexagon e não é apropriado como runtime universal. O aparelho SM-M536B é um Galaxy M53 com MediaTek Dimensity 900, portanto este projeto passa a compilar o llama.cpp pelo Android NDK para CPU ARM64 genérica, sem dependências Qualcomm, OpenCL ou OpenSSL.

O build segue as opções Android documentadas pelo projeto oficial llama.cpp, incluindo `GGML_NATIVE=OFF`, `GGML_OPENMP=OFF`, `GGML_LLAMAFILE=OFF` e `LLAMA_OPENSSL=OFF`. `GGML_CPU_KLEIDIAI=ON` disponibiliza kernels Arm compatíveis que o runtime seleciona conforme o hardware.

## Gerar e testar o APK

No GitHub, abra **Actions > APK Android ARM64 (CPU) > Run workflow**. Depois de a execução terminar com sucesso, baixe o artefato `majeirkn-apk-arm64-cpu`.

O arquivo gerado é um APK de depuração. A compilação precisa ser seguida de instalação e teste no aparelho; o desempenho e o tamanho de modelo suportado dependem da memória e do processador disponíveis. O APK não inclui um modelo GGUF.
