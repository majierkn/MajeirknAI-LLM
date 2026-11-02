"""Leitura e validacao do config.json da Majeirkn AI.

As chaves originais (model_path, context_size, threads, temperature, top_p,
repeat_penalty, enable_thinking, system_prompt) continuam validas. As chaves
novas sao opcionais: quando ausentes, entram os valores de DEFAULTS.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"

DEFAULTS: dict[str, Any] = {
    # Amostragem
    "temperature": 0.7,
    "top_p": 0.8,
    "top_k": 40,
    "min_p": 0.05,
    "repeat_penalty": 1.1,
    "max_tokens": 512,
    "enable_thinking": False,
    # Desempenho
    "context_size": 2048,
    "threads": None,  # None = autodetectar
    "batch_size": 512,
    "ubatch_size": 128,
    "flash_attn": "auto",
    "cache_type_k": "f16",
    "cache_type_v": "f16",
    "parallel": 1,
    # Servidor local
    "host": "127.0.0.1",
    "port": 8081,
    "web_ui": "majeirkn",  # "majeirkn" = nossa pagina; "oficial" = UI do llama.cpp; "nenhuma"
    "use_slot_cache": True,
    # Armazenamento
    "data_dir": "~/.majeirkn",
}

# Chaves que precisam existir e ter o tipo certo.
REQUIRED: dict[str, Any] = {
    "model_path": str,
    "system_prompt": str,
    "temperature": (int, float),
    "top_p": (int, float),
    "repeat_penalty": (int, float),
}

CACHE_TYPES = {"f32", "f16", "bf16", "q8_0", "q4_0", "q4_1", "iq4_nl", "q5_0", "q5_1"}

WEB_UI_MODES = {"majeirkn", "oficial", "nenhuma"}


class ConfigError(RuntimeError):
    """Configuracao ausente, malformada ou com valores fora de faixa."""


def _is_int(value: Any) -> bool:
    # bool herda de int em Python; threads=true nao pode passar por int.
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Le o config.json, aplica os padroes e valida os valores."""
    path = Path(path) if path else CONFIG_PATH
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError as exc:
        raise ConfigError(f"Arquivo de configuracao nao encontrado: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"JSON invalido em {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError(f"O config.json deve conter um objeto JSON: {path}")

    config: dict[str, Any] = {**DEFAULTS, **data}
    _validate(config)
    return config


def validate(config: dict[str, Any]) -> None:
    """Valida um dicionario de configuracao ja mesclado com os padroes."""
    _validate(config)


def _validate(config: dict[str, Any]) -> None:
    for key in REQUIRED:
        if key not in config:
            raise ConfigError(f"Chave obrigatoria ausente no config: '{key}'")

    if not isinstance(config["model_path"], str) or not config["model_path"].strip():
        raise ConfigError("model_path deve ser um caminho nao vazio.")
    if not isinstance(config["system_prompt"], str) or not config["system_prompt"].strip():
        raise ConfigError("system_prompt deve ser um texto nao vazio.")

    for key in ("temperature", "top_p", "repeat_penalty"):
        if not _is_number(config[key]):
            raise ConfigError(f"'{key}' deve ser um numero.")
    if not 0.0 < float(config["temperature"]) <= 2.0:
        raise ConfigError("temperature deve estar entre 0 (exclusivo) e 2.")
    if not 0.0 < float(config["top_p"]) <= 1.0:
        raise ConfigError("top_p deve estar entre 0 (exclusivo) e 1.")
    if float(config["repeat_penalty"]) < 1.0:
        raise ConfigError("repeat_penalty deve ser maior ou igual a 1.")

    if not _is_int(config["context_size"]) or config["context_size"] < 512:
        raise ConfigError("context_size deve ser um inteiro de pelo menos 512.")
    if config["threads"] is not None and (not _is_int(config["threads"]) or config["threads"] < 1):
        raise ConfigError("threads deve ser um inteiro de pelo menos 1, ou null para autodetectar.")
    if not _is_int(config["batch_size"]) or config["batch_size"] < 1:
        raise ConfigError("batch_size deve ser um inteiro positivo.")
    if not _is_int(config["ubatch_size"]) or config["ubatch_size"] < 1:
        raise ConfigError("ubatch_size deve ser um inteiro positivo.")
    if config["ubatch_size"] > config["batch_size"]:
        raise ConfigError("ubatch_size nao pode ser maior que batch_size.")
    if config["flash_attn"] not in {"on", "off", "auto"}:
        raise ConfigError("flash_attn deve ser 'on', 'off' ou 'auto'.")
    for key in ("cache_type_k", "cache_type_v"):
        if config[key] not in CACHE_TYPES:
            raise ConfigError(f"{key} deve ser um de: {', '.join(sorted(CACHE_TYPES))}.")
    if not _is_int(config["port"]) or not 1024 <= config["port"] <= 65535:
        raise ConfigError("port deve ser um inteiro entre 1024 e 65535.")
    if config["web_ui"] not in WEB_UI_MODES:
        raise ConfigError(f"web_ui deve ser um de: {', '.join(sorted(WEB_UI_MODES))}.")
    if not _is_int(config["parallel"]) or config["parallel"] < 1:
        raise ConfigError("parallel deve ser um inteiro de pelo menos 1.")
    if not _is_int(config["max_tokens"]) or config["max_tokens"] < -1:
        raise ConfigError("max_tokens deve ser -1 (sem limite) ou um inteiro positivo.")


def resolve_model_path(config: dict[str, Any], root: Path | None = None) -> Path:
    """Resolve o caminho do GGUF contra a raiz do projeto."""
    root = Path(root) if root else ROOT
    return (root / config["model_path"]).resolve()


def auto_threads() -> int:
    """Threads de inferencia sem travar o Android: deixa 2 nucleos para o sistema."""
    return max(1, min(8, (os.cpu_count() or 4) - 2))


def resolve_threads(config: dict[str, Any]) -> int:
    """threads do config se definido; caso contrario, autodetecao."""
    threads = config.get("threads")
    if _is_int(threads) and threads >= 1:
        return int(threads)
    return auto_threads()


def data_dir(config: dict[str, Any]) -> Path:
    """Pasta de sessoes, logs e checkpoints (padrao: $HOME/.majeirkn)."""
    env = os.environ.get("MAJEIRKN_HOME")
    raw = env if env else str(config.get("data_dir") or DEFAULTS["data_dir"])
    path = Path(raw).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def available_memory_mb() -> int | None:
    """Memoria disponivel em MB lida de /proc/meminfo (None se indisponivel)."""
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as file:
            for line in file:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) // 1024
    except OSError:
        return None
    return None


def memory_warning(config: dict[str, Any], model_path: Path) -> str | None:
    """Aviso quando a RAM livre nao acomoda modelo + cache de contexto."""
    available = available_memory_mb()
    if available is None or not model_path.is_file():
        return None

    model_mb = model_path.stat().st_size / (1024 * 1024)
    # Margem rude: 1 GB de folga para o cache de contexto e o proprio sistema.
    needed_mb = model_mb * 1.25 + 1024 * (0.5 if config["flash_attn"] == "on" else 0.75)
    if available < needed_mb:
        return (
            f"Memoria livre (~{available} MB) abaixo do necessario (~{needed_mb:.0f} MB) "
            f"para o modelo de {model_mb:.0f} MB. Feche aplicativos ou reduza context_size."
        )
    return None


def sampling_params(config: dict[str, Any]) -> dict[str, Any]:
    """Parametros de amostragem enviados em cada request ao llama-server."""
    return {
        "temperature": float(config["temperature"]),
        "top_p": float(config["top_p"]),
        "top_k": int(config["top_k"]),
        "min_p": float(config["min_p"]),
        "repeat_penalty": float(config["repeat_penalty"]),
        "max_tokens": int(config["max_tokens"]),
    }
