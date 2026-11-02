"""Teste de fumaca: sobe o llama-server e conversa de verdade (uso manual)."""
from __future__ import annotations

import sys

from majeirkn import config as config_mod
from majeirkn.client import ChatClient, ServerError
from majeirkn.server import LlamaServer, find_llama_server


def main() -> int:
    config = config_mod.load_config()
    model_path = config_mod.resolve_model_path(config)
    llama_server = find_llama_server()
    if llama_server is None:
        print("llama-server nao encontrado")
        return 2

    data_dir = config_mod.data_dir(config)
    log_path = data_dir / "logs" / "smoke.log"
    server = LlamaServer(config, model_path, llama_server, log_path=log_path)
    print("iniciando servidor ...", flush=True)
    try:
        server.start(timeout=900)
    except Exception as exc:  # noqa: BLE001 - queremos ver o erro completo
        print(f"falha ao iniciar: {exc}")
        return 1

    print(f"pronto em {server.base_url} ({server.startup_seconds:.1f}s para carregar)")
    client = ChatClient(server.base_url)

    messages = [
        {"role": "system", "content": config["system_prompt"]},
        {"role": "user", "content": "Em uma frase: o que e memoria virtual?"},
    ]
    try:
        pieces = []
        for event in client.chat_stream(messages, config_mod.sampling_params(config)):
            if event["type"] == "delta":
                pieces.append(event["text"])
            elif event["type"] == "done":
                print("\n--- usage:", event["usage"])
                print("--- timings:", event["timings"])
                print(f"--- tempo total: {event['seconds']:.1f}s")
        print("resposta:", "".join(pieces)[:400])
    except ServerError as exc:
        print(f"erro no chat: {exc}")
        return 1

    # Checkpoint de contexto: salvar e restaurar no mesmo servidor.
    if server.save_slot("smoke.slot"):
        print("checkpoint salvo ok")
    else:
        print("checkpoint falhou (ver log)")
    print("RAM do processo (MB):", server.rss_mb(), "pico:", server.peak_rss_mb())
    server.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
