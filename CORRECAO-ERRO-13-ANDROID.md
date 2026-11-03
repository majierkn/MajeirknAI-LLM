# Correção do erro 13 e runtime Snapdragon ARM64

O erro error=13: Permission denied ocorria porque o Android não permitia iniciar o executável a partir de uma pasta gravável privada (files/bin).

## Correções aplicadas

- O executável ARM64 é empacotado em android/app/src/main/jniLibs/arm64-v8a/libllama-server.so.
- O Android extrai o binário em ApplicationInfo.nativeLibraryDir; o serviço o inicia desse local.
- As bibliotecas do runtime são copiadas dos assets para files/bin.
- O workflow foi ajustado à estrutura llama.cpp/bin/libllama-server.so e llama.cpp/lib/*.so.
- A validação confere AArch64 nas bibliotecas de processo e não classifica os blobs Qualcomm DSP6 como ELF ARM64.
- O workflow não exige libssl.so.3 ou libcrypto.so.3, pois essas bibliotecas não aparecem como dependências ELF do servidor recebido.

## Gerar o APK

Publique o runtime .tar.gz em um local com link direto e execute Actions > APK Android ARM64 > Run workflow, preenchendo runtime_url, ou configure o segredo MAJEIRKN_RUNTIME_URL.

O runtime contém uma dependência libOpenCL.so que precisa existir e estar acessível pelo driver Qualcomm do aparelho. O APK só pode ser considerado pronto após a compilação no GitHub Actions e um teste em dispositivo Snapdragon compatível.
