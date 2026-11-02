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

A compilação acontece em `$HOME/majeirkn-build` (armazenamento privado do Termux). Não compile dentro da pasta do projeto quando ela estiver em `/storage/emulated/0`: esse armazenamento compartilhado não aceita links simbólicos e a compilação falha com `Permission denied`. Se o `llama-cli` foi compilado por você em outro caminho, use a variável `LLAMA_CLI`.

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

Na tela de conversa, escreva sua pergunta e dê Enter. Para sair, digite `/exit`, use `Ctrl+C` ou feche o Termux.

## Interface web (recomendado no celular)

O projeto traz uma página própria, servida pelo próprio `llama-server`:

```bash
python main.py --web
```

Ao carregar, o programa mostra o endereço (padrão `http://localhost:8081`) e
tenta abrir o navegador. A página tem streaming token a token, botão de parar,
ajustes de criatividade, conversas salvas no próprio navegador e funciona
offline. No Chrome, use o menu **"Adicionar à tela inicial"** para instalá-la
como um aplicativo.

Para usar a interface web oficial do llama.cpp em vez da nossa, mude
`web_ui` para `"oficial"` no `config.json`. As duas são mutualmente exclusivas
no mesmo endereço.

### Atalho de um toque

```bash
mkdir -p ~/.shortcuts/tasks
cp scripts/atalho.sh ~/.shortcuts/tasks/MajeirknAI.sh
chmod +x ~/.shortcuts/tasks/MajeirknAI.sh
```

Depois adicione o widget **Termux:Widget** na tela inicial e escolha
`MajeirknAI.sh`. Um toque liga o servidor e abre o navegador.

### Comandos do terminal

No modo terminal (`python main.py`), digite `/help` para ver os comandos:
`/new`, `/resume`, `/sessions`, `/save`, `/export`, `/title`, `/params`,
`/set`, `/model`, `/slots`, `/clear` e `/exit`.

## Instalação para amigos

O pacote foi feito para instalar sem compilar nada no aparelho.

**O que o amigo precisa:** Android 8 ou mais recente, arquitetura `arm64`,
Termux instalado, cerca de 2,5 GB de espaço livre e Wi-Fi para baixar o modelo.

### Caminho 1 — link direto (um comando)

```bash
curl -fsSL <link>/bootstrap.sh | bash
bash ~/MajeirknAI-LLM/scripts/download_model.sh   # ~1,31 GB
python ~/MajeirknAI-LLM/main.py --web
```

### Caminho 2 — pelo repositório

```bash
pkg install -y git curl
git clone <url-do-repositorio> MajeirknAI-LLM
cd MajeirknAI-LLM
bash scripts/install.sh
bash scripts/download_model.sh
python main.py --web
```

O `scripts/install.sh` baixa o pacote de runtime pronto (~9,5 MB) e o instala.
Se o binário não servir no aparelho dele, o script compila do fonte
automaticamente (`scripts/install_termux.sh`), o que leva de 30 a 60 minutos.

### Caminho 3 — aplicativo Android

Veja `android/README.md`: o APK empacota o mesmo runtime e abre a mesma
interface web, sem Termux.

## Medir velocidade e memória

```bash
python main.py --bench                    # variantes padrao
python main.py --bench --variants base,fa_on,kv_q8,threads6
```

O benchmark inicia o servidor com cada configuração, mede tempo de carga,
velocidade de prompt e de geração e o pico de RAM, e salva o resultado em
`<data_dir>/bench/`.

## Ajustes

Edite `config.json`:

- `context_size`: comece em `2048`; não aumente antes de confirmar que há memória disponível.
- `threads`: comece em `4`; `null` deixa o programa escolher (deixa 2 núcleos para o sistema).
- `temperature`, `top_p`, `top_k`, `min_p`, `repeat_penalty`, `max_tokens`: amostragem das respostas. Também podem ser mudados em tempo real com `/set` no terminal ou pelos controles da interface web.
- `enable_thinking`: liga/desliga o modo de raciocínio do Qwen3. Mantenha `false` no celular: o "pensamento" gasta tokens do contexto e deixa a resposta mais lenta.
- `system_prompt`: instruções permanentes da Majeirkn AI (a interface web lê `majeirkn/ui/system.txt`, que precisa ter o mesmo texto — um teste garante isso).
- `host`, `port`: onde o servidor local escuta.
- `web_ui`: `"majeirkn"` (nossa página), `"oficial"` (a do llama.cpp, se o binário foi compilado com ela) ou `"nenhuma"`.
- `batch_size`, `ubatch_size`, `flash_attn`, `cache_type_k/v`, `parallel`: desempenho. Meça antes de mudar (`python main.py --bench`).
- `use_slot_cache`: grava o contexto em disco para retomar conversas sem reprocessar tudo.
- `data_dir`: onde ficam sessões, logs e checkpoints (padrão `~/.majeirkn`; a variável `MAJEIRKN_HOME` sobrescreve).

Se `llama-cli` já estiver instalado em outro caminho, defina a variável `LLAMA_CLI`. Para o servidor, use `LLAMA_SERVER` com o caminho completo.

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

1. Testar o APK em um aparelho real (o build sai pela CI, veja `android/README.md`).
2. Medir as variantes de desempenho no aparelho-alvo com `python main.py --bench` e fixar a melhor configuração.
3. RAG: indexar documentos locais e injetar os trechos relevantes nas respostas.
4. Construir um dataset próprio em português e avaliar fine-tuning/LoRA em PC ou GPU na nuvem — não no telefone.
5. Testes de qualidade automatizados das respostas (comparação antes/depois de cada mudança).

## Testes

```bash
python -m unittest discover -s tests -t .
```

Cobrem a validação do `config.json`, o armazenamento de sessões, o comando do
servidor e os arquivos da interface web (inclusive o PWA e o prompt de sistema).
