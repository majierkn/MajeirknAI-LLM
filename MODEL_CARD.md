# Cartão do modelo — configuração da Majeirkn AI

| Campo | Valor |
|---|---|
| Nome da aplicação | Majeirkn AI |
| Modelo subjacente | Qwen3.5-2B |
| Quantização | Q4_K_M |
| Formato | GGUF |
| Arquivo | Qwen3.5-2B-Q4_K_M.gguf |
| Tamanho publicado | Aproximadamente 1,31 GB |
| Runtime | llama.cpp |
| Idioma de interface | Português do Brasil |
| Execução | Local no dispositivo após instalação |
| Contexto inicial | 2.048 tokens |

## Proveniência

Os pesos vêm de uma conversão GGUF de terceiros do modelo Qwen3.5-2B. A conversão altera o formato e a precisão numérica para inferência; não é um treinamento independente nem um fine-tuning feito por este projeto.

Consulte a ficha e a licença do modelo original antes de uso ou redistribuição: https://huggingface.co/Qwen/Qwen3.5-2B

Conversão usada: https://huggingface.co/SoAIHQ/Qwen3.5-2B-GGUF

## Limitações conhecidas

- Este protótipo está orientado a texto; não configura o projetor multimodal separado.
- Não inclui navegação na internet, pesquisa em tempo real ou acesso a arquivos do usuário.
- Pode produzir respostas incorretas ou inventar detalhes.
- O uso de RAM, aquecimento e velocidade ainda precisam de medição no aparelho-alvo.
