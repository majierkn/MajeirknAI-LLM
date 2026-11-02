"""Benchmark local: mede carga do modelo, velocidade de geracao e uso de RAM.

Cada variante inicia o llama-server com parametros proprios, faz dois pedidos
(um curto e um com historico, para medir o reuso do prefixo no cache) e depois
encerra o processo. Os resultados ficam em <data_dir>/bench/.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config as config_mod
from .client import ChatClient, ServerError
from .server import LlamaServer, ServerError as ServerStartError, find_llama_server

# Variantes comparadas. Cada uma aplica overrides sobre o config.json.
VARIANTS: dict[str, dict[str, Any]] = {
    "base": {},
    "threads6": {"threads": 6},
    "threads4": {"threads": 4},
    "fa_on": {"flash_attn": "on"},
    "fa_off": {"flash_attn": "off"},
    "kv_q8": {"cache_type_k": "q8_0", "cache_type_v": "q8_0"},
    "ctx3072": {"context_size": 3072},
}

SHORT_MESSAGE = "Explique em duas frases o que é memoria virtual em um celular."
FOLLOWUP = "Diga uma desvantagem disso."
SYSTEM = "Voce e um assistente direto. Responda em portugues do Brasil."


def _tokens_per_second(timings: dict[str, Any]) -> float | None:
    predicted_n = timings.get("predicted_n")
    predicted_ms = timings.get("predicted_ms")
    if not isinstance(predicted_n, int) or not isinstance(predicted_ms, (int, float)):
        return None
    if predicted_ms <= 0:
        return None
    return predicted_n / (predicted_ms / 1000.0)


def _run_turn(
    client: ChatClient,
    messages: list[dict[str, str]],
    max_tokens: int,
) -> dict[str, Any]:
    params = {
        "temperature": 0.6,
        "top_p": 0.8,
        "top_k": 40,
        "min_p": 0.05,
        "repeat_penalty": 1.1,
        "max_tokens": max_tokens,
        "cache_prompt": True,
    }
    result = client.chat_once(messages, params)
    timings = result["timings"]
    return {
        "prompt_tokens": result["usage"].get("prompt_tokens"),
        "completion_tokens": result["usage"].get("completion_tokens"),
        "prompt_ms": timings.get("prompt_ms"),
        "prompt_tps": (
            timings["prompt_n"] / (timings["prompt_ms"] / 1000.0)
            if timings.get("prompt_n") and timings.get("prompt_ms", 0) > 0
            else None
        ),
        "predicted_ms": timings.get("predicted_ms"),
        "gen_tps": _tokens_per_second(timings),
    }


def run_variant(
    name: str,
    overrides: dict[str, Any],
    config: dict[str, Any],
    model_path: Path,
    llama_server: Path,
    data_dir: Path,
    max_tokens: int = 96,
) -> dict[str, Any]:
    """Roda uma variante completa do benchmark e devolve as medicoes."""
    bench_config = {**config, **overrides}
    config_mod.validate(bench_config)
    # threads explicito evita surpresa entre variantes em maquinas grandes
    if bench_config.get("threads") is None:
        bench_config["threads"] = config_mod.resolve_threads(bench_config)

    log_path = data_dir / "bench" / f"{name}.log"
    entry: dict[str, Any] = {"variant": name, "overrides": overrides}

    server = LlamaServer(bench_config, model_path, llama_server, log_path=log_path)
    try:
        server.start()
    except ServerStartError as exc:
        return {**entry, "error": str(exc)}

    try:
        entry["startup_s"] = round(server.startup_seconds or 0.0, 2)
        client = ChatClient(server.base_url)
        messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": SHORT_MESSAGE}]
        try:
            first = _run_turn(client, messages, max_tokens)
        except ServerError as exc:
            return {**entry, "error": str(exc)}

        messages.append({"role": "assistant", "content": "ok"})
        messages.append({"role": "user", "content": FOLLOWUP})
        try:
            second = _run_turn(client, messages, max_tokens)
        except ServerError as exc:
            entry["turn1"] = first
            return {**entry, "error": str(exc)}

        entry["turn1"] = first
        entry["turn2_prefix_reuse"] = second
        entry["peak_rss_mb"] = server.peak_rss_mb()
    finally:
        server.stop()

    entry["threads"] = bench_config["threads"]
    entry["flash_attn"] = bench_config["flash_attn"]
    entry["context_size"] = bench_config["context_size"]
    return entry


def format_report(entries: list[dict[str, Any]]) -> str:
    """Monta a tabela de resultados em texto puro."""
    header = (
        f"{'variante':<12}{'threads':>8}{'ctx':>6}{'carga(s)':>10}"
        f"{'prompt(tok)':>13}{'prompt_tps':>12}{'gen_tps':>9}{'RAM(MB)':>9}"
    )
    lines = [header, "-" * len(header)]
    for entry in entries:
        if "error" in entry:
            lines.append(f"{entry['variant']:<12}FALHOU: {entry['error']}")
            continue
        turn1 = entry.get("turn1", {})
        turn2 = entry.get("turn2_prefix_reuse", {})
        lines.append(
            f"{entry['variant']:<12}{entry.get('threads', '?'):>8}{entry.get('context_size', '?'):>6}"
            f"{entry.get('startup_s', 0):>10.1f}"
            f"{str(turn1.get('prompt_tokens') or '?'):>13}"
            f"{(turn1.get('prompt_tps') or 0):>12.1f}"
            f"{(turn2.get('gen_tps') or turn1.get('gen_tps') or 0):>9.1f}"
            f"{(entry.get('peak_rss_mb') or 0):>9.0f}"
        )
    return "\n".join(lines)


def main(
    config_path: Path | None = None,
    variants: list[str] | None = None,
    max_tokens: int = 96,
) -> int:
    """Ponto de entrada do benchmark."""
    config = config_mod.load_config(config_path)
    model_path = config_mod.resolve_model_path(config)
    data_dir = config_mod.data_dir(config)

    llama_server = find_llama_server()
    if llama_server is None:
        print("[Majeirkn AI] llama-server nao encontrado.")
        print("Execute: bash scripts/install_termux.sh")
        return 2
    if not model_path.is_file():
        print(f"[Majeirkn AI] Modelo GGUF nao encontrado: {model_path}")
        return 2

    wanted = list(variants) if variants else ["base", "fa_on", "kv_q8", "threads6"]
    unknown = [name for name in wanted if name not in VARIANTS]
    if unknown:
        print(f"Variantes desconhecidas: {', '.join(unknown)}")
        print(f"Disponiveis: {', '.join(VARIANTS)}")
        return 2

    print("Majeirkn AI - benchmark local")
    print(f"Modelo: {model_path}")
    print(f"Variantes: {', '.join(wanted)}\n")

    entries = []
    for name in wanted:
        print(f"medindo {name} ...", flush=True)
        entries.append(
            run_variant(
                name, VARIANTS[name], config, model_path, llama_server, data_dir, max_tokens
            )
        )
        print(format_report([entries[-1]]), "\n", flush=True)

    report = format_report(entries)
    print(report)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_path = data_dir / "bench" / f"bench-{stamp}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResultados salvos em {out_path}")
    return 0
