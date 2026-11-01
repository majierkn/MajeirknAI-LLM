#!/usr/bin/env python3
"""Launcher local para o Majeirkn AI usando llama.cpp e um modelo GGUF."""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"


def load_config() -> dict[str, Any]:
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as file:
            config = json.load(file)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Arquivo de configuração não encontrado: {CONFIG_PATH}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"JSON inválido em {CONFIG_PATH}: {exc}") from exc

    required = {
        "model_path": str,
        "context_size": int,
        "threads": int,
        "temperature": (int, float),
        "top_p": (int, float),
        "repeat_penalty": (int, float),
        "system_prompt": str,
    }
    for key, expected_type in required.items():
        if key not in config or not isinstance(config[key], expected_type):
            raise RuntimeError(f"Configuração inválida: '{key}' ausente ou com tipo incorreto.")

    if config["context_size"] < 512:
        raise RuntimeError("context_size deve ser pelo menos 512.")
    if config["threads"] < 1:
        raise RuntimeError("threads deve ser pelo menos 1.")
    return config


def find_llama_cli() -> Path | None:
    override = os.environ.get("LLAMA_CLI")
    candidates = [
        Path(override).expanduser() if override else None,
        Path.home() / "majeirkn-build" / "bin" / "llama-cli",
        ROOT / "vendor" / "llama.cpp" / "build" / "bin" / "llama-cli",
        ROOT / "llama.cpp" / "build" / "bin" / "llama-cli",
    ]
    for candidate in candidates:
        if candidate and candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()

    located = shutil.which("llama-cli")
    return Path(located).resolve() if located else None


def main() -> int:
    try:
        config = load_config()
    except RuntimeError as exc:
        print(f"[Majeirkn AI] {exc}", file=sys.stderr)
        return 2

    model_path = (ROOT / config["model_path"]).resolve()
    if not model_path.is_file():
        print("[Majeirkn AI] Modelo GGUF não encontrado.", file=sys.stderr)
        print(f"Caminho esperado: {model_path}", file=sys.stderr)
        print("Execute: bash scripts/download_model.sh", file=sys.stderr)
        return 2

    llama_cli = find_llama_cli()
    if llama_cli is None:
        print("[Majeirkn AI] llama-cli não encontrado.", file=sys.stderr)
        print("Execute: bash scripts/install_termux.sh", file=sys.stderr)
        print("Ou, se já compilou em outro lugar:", file=sys.stderr)
        print("  export LLAMA_CLI=/caminho/para/llama-cli", file=sys.stderr)
        return 2

    # Nesta versao do llama.cpp o modo conversa e interativo por padrao
    # (a flag -cnv foi removida das versoes novas).
    command = [
        str(llama_cli),
        "-m", str(model_path),
        "-c", str(config["context_size"]),
        "-t", str(config["threads"]),
        "--temp", str(config["temperature"]),
        "--top-p", str(config["top_p"]),
        "--repeat-penalty", str(config["repeat_penalty"]),
    ]

    # Modelos Qwen3.x ligam o "thinking" por padrao, o que gasta tokens do
    # contexto e deixa a resposta lenta no celular. Deixe false por padrao.
    if config.get("enable_thinking", False):
        command += ["-rea", "on"]
    else:
        command += ["-rea", "off"]

    command += ["-sys", config["system_prompt"]]
    print("Majeirkn AI — inferência local", flush=True)
    print("Modelo carregando... a primeira resposta pode levar alguns segundos.")
    print("Digite /exit ou Ctrl+C para sair.\n", flush=True)
    try:
        os.execv(str(llama_cli), command)
    except OSError as exc:
        print(f"Não foi possível iniciar llama-cli: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
