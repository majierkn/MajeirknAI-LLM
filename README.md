# Majeirkn AI — LLM local (protótipo v0.1)

Projeto inicial para executar um modelo de linguagem localmente no Android/Termux, sem chave de API e sem enviar as conversas para um servidor remoto.

## O que este projeto é

- Interface de conversa no terminal, em português do Brasil.
- Inferência local com `llama.cpp`.
- Modelo-base configurado: **Qwen3.5-2B Q4_K_M (GGUF)**.
- Configuração conservadora inicial para um aparelho com 8 GB de RAM: contexto de 2.048 tokens e quatro threads. Ajuste depois de medir temperatura, memória e velocidade no aparelho.
- O arquivo de pesos não vem dentro do ZIP: são aproximadamente 1,31 GB e devem ser baixados separadamente.

## O que ele ainda não é

Este pacote **não contém um LLM treinado do zero**, nem um APK Android. Ele é um protótipo de execução local que usa os pesos pré-treinados do Qwen3.5-2B. O nome Majeirkn AI, o prompt de sistema e o launcher são a camada inicial personalizada. Para mudar o conhecimento ou o comportamento profundamente, será necessário preparar um conjunto de dados e fazer fine-tuning em hardware adequado.

## Requisitos

- Android com Termux instalado de uma fonte confiável (projeto oficial do Termux ou F-Droid).
- Arquitetura ARM64 (`arm64-v8a`).
- Internet apenas durante a instalação/download inicial; depois da instalação e do download dos pesos, a geração é local.
- Aproximadamente 1,31 GB para o arquivo GGUF, além do espaço necessário para compilar `llama.cpp` e armazenar os arquivos temporários.

## Instalação no Termux

Entre na pasta do projeto e execute:

```bash
chmod +x run.sh scripts/*.sh
bash scripts/install_termux.sh
```

A compilação é feita no próprio aparelho e pode consumir bastante RAM, aquecer o telefone ou ser encerrada pelo Android. Feche aplicativos pesados, mantenha o aparelho ventilado e use `-j2` (já configurado) para reduzir o pico de consumo.

Baixe o modelo:

```bash
bash scripts/download_model.sh
```

Inicie a conversa:

```bash
python main.py
```

ou:

```bash
bash run.sh
```

Para sair, pressione `Ctrl+C`.

## Ajustes

Edite `config.json`:

- `context_size`: comece em `2048`; não aumente antes de confirmar que há memória disponível.
- `threads`: comece em `4`; mais threads nem sempre significam mais velocidade.
- `temperature`: controla a variação das respostas.
- `top_p`: controla a amostragem.
- `system_prompt`: instruções permanentes da Majeirkn AI.

Se `llama-cli` já estiver instalado em outro caminho, defina a variável `LLAMA_CLI` com o caminho completo antes de iniciar.

## Privacidade e limites

A inferência acontece localmente com o binário `llama.cpp` e o arquivo GGUF. Este launcher não inclui telemetria nem chamadas a APIs. A instalação e o download do modelo obviamente precisam de internet. A qualidade e a velocidade dependem do chip, da memória disponível, da temperatura do aparelho e da versão do runtime.

Modelos pequenos podem errar fatos, cálculos ou instruções complexas. Não use as respostas como única fonte para decisões médicas, jurídicas ou financeiras.

## Modelo-base e licença

- Modelo original: [Qwen/Qwen3.5-2B](https://huggingface.co/Qwen/Qwen3.5-2B)
- Conversão GGUF: [SoAIHQ/Qwen3.5-2B-GGUF](https://huggingface.co/SoAIHQ/Qwen3.5-2B-GGUF)
- Arquivo escolhido: `Qwen3.5-2B-Q4_K_M.gguf` (aprox. 1,31 GB).
- Licença indicada pelo repositório do modelo: Apache-2.0. Consulte também os termos e a ficha do modelo original antes de redistribuir pesos.
- Runtime: [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp), com documentação para Android.

A conversão GGUF não significa que este projeto treinou ou criou os pesos originais. Créditos aos autores do Qwen e aos mantenedores do `llama.cpp`.

## Próximas etapas sugeridas

1. Validar execução, velocidade e uso de RAM no Galaxy M53.
2. Criar uma interface Android nativa em Kotlin e integrar o backend C++ por JNI.
3. Construir um dataset próprio em português e avaliar fine-tuning/LoRA em PC ou GPU na nuvem — não no telefone.
4. Acrescentar histórico local, exportação de conversas e testes de qualidade.
