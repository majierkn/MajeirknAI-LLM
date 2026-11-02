"""Gerencia o processo local do llama-server: inicio, parada e checkpoints."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from . import config as config_mod

ROOT = config_mod.ROOT


class ServerError(RuntimeError):
    """Falha ao iniciar ou conversar com o llama-server."""


def find_llama_server() -> Path | None:
    """Procura o binario do llama-server nos lugares conhecidos."""
    override = os.environ.get("LLAMA_SERVER")
    candidates = [
        Path(override).expanduser() if override else None,
        Path.home() / "majeirkn-build" / "bin" / "llama-server",
        ROOT / "vendor" / "llama.cpp" / "build" / "bin" / "llama-server",
        ROOT / "llama.cpp" / "build" / "bin" / "llama-server",
    ]
    for candidate in candidates:
        if candidate and candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()

    located = shutil.which("llama-server")
    return Path(located).resolve() if located else None


class LlamaServer:
    """Processo do llama-server com espera de /health e checkpoint de slot."""

    def __init__(
        self,
        config: dict[str, Any],
        model_path: Path,
        llama_server: Path,
        log_path: Path | None = None,
        public_path: Path | None = None,
    ) -> None:
        self.config = config
        self.model_path = model_path
        self.binary = llama_server
        self.log_path = log_path
        # Diretorio de arquivos estaticos servido em "/" (nossa pagina web).
        self.public_path = public_path
        self.process: subprocess.Popen | None = None
        self.started_at: float | None = None
        self.ready_at: float | None = None
        self._log_handle = None

    # ---------------------------------------------------------------- comandos

    @property
    def base_url(self) -> str:
        return f"http://{self.config['host']}:{self.config['port']}"

    def build_command(self) -> list[str]:
        """Monta a linha de comando do llama-server a partir do config."""
        cfg = self.config
        command = [
            str(self.binary),
            "--model", str(self.model_path),
            "--ctx-size", str(cfg["context_size"]),
            "--threads", str(config_mod.resolve_threads(cfg)),
            "--threads-batch", str(config_mod.resolve_threads(cfg)),
            "--batch-size", str(cfg["batch_size"]),
            "--ubatch-size", str(cfg["ubatch_size"]),
            "--flash-attn", str(cfg["flash_attn"]),
            "--cache-type-k", str(cfg["cache_type_k"]),
            "--cache-type-v", str(cfg["cache_type_v"]),
            "--parallel", str(cfg["parallel"]),
            "--host", str(cfg["host"]),
            "--port", str(cfg["port"]),
            "--temp", str(cfg["temperature"]),
            "--top-p", str(cfg["top_p"]),
            "--top-k", str(cfg["top_k"]),
            "--min-p", str(cfg["min_p"]),
            "--repeat-penalty", str(cfg["repeat_penalty"]),
            "--no-warmup",
        ]

        # Qwen3.x pensa por padrao; reasoning-budget 0 desliga o modo pensamento.
        if not cfg.get("enable_thinking", False):
            command += ["--reasoning-budget", "0"]

        if cfg.get("use_slot_cache", True):
            # O llama-server exige que o diretorio de checkpoints ja exista.
            slots_dir = config_mod.data_dir(cfg) / "slots"
            try:
                slots_dir.mkdir(parents=True, exist_ok=True)
                command += ["--slot-save-path", str(slots_dir)]
            except OSError:
                pass  # sem a pasta, o servidor so funciona sem checkpoint

        # "majeirkn": serve nossa pagina em "/" pelo --path. "oficial": deixa o
        # servidor usar a UI embutida (se foi compilada com ela).
        ui_mode = cfg.get("web_ui", "majeirkn")
        if ui_mode == "majeirkn" and self.public_path is not None:
            if not self.public_path.is_dir():
                raise ServerError(
                    f"Diretorio da interface web nao encontrado: {self.public_path}"
                )
            command += ["--path", str(self.public_path)]

        command += list(cfg.get("extra_args", []))
        return command

    # ------------------------------------------------------------------ ciclo

    def start(self, timeout: float = 600.0) -> None:
        """Inicia o servidor e espera ate /health responder 200."""
        if self.process is not None:
            raise ServerError("O servidor ja esta em execucao.")

        if self.log_path is not None:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_handle = self.log_path.open("a", encoding="utf-8", buffering=1)

        # Se algo ja responde na porta, o processo filho morreria com
        # "address in use" e o health daria falso positivo no servidor alheio.
        if self.health():
            raise ServerError(
                f"Ja existe um servidor respondendo em {self.base_url}. "
                "Use --attach para conversar com ele ou mude 'port' no config.json."
            )

        self.started_at = time.monotonic()
        try:
            self.process = subprocess.Popen(
                self.build_command(),
                stdout=self._log_handle or subprocess.DEVNULL,
                stderr=subprocess.STDOUT if self._log_handle else subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                cwd=str(ROOT),
            )
        except OSError as exc:
            raise ServerError(f"Nao foi possivel iniciar o llama-server: {exc}") from exc

        if not self.wait_ready(timeout):
            detail = self._log_tail()
            self.stop()
            raise ServerError(
                "O llama-server nao ficou pronto dentro do tempo limite.\n"
                f"Porta: {self.config['port']}\n{detail}"
            )
        self.ready_at = time.monotonic()

    def wait_ready(self, timeout: float) -> bool:
        """Consulta /health até responder 200 ou estourar o tempo."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.process is not None and self.process.poll() is not None:
                return False  # processo morreu
            if self.health():
                return True
            time.sleep(1.0)
        return False

    def health(self) -> bool:
        """GET /health; 200 significa pronto para receber requests."""
        try:
            with urllib.request.urlopen(f"{self.base_url}/health", timeout=5) as response:
                return response.status == 200
        except (urllib.error.URLError, OSError):
            return False

    def stop(self) -> None:
        """Encerra o processo com terminate e, se preciso, kill."""
        process = self.process
        self.process = None
        if process is None:
            return
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        if self._log_handle is not None:
            self._log_handle.close()
            self._log_handle = None

    def __enter__(self) -> "LlamaServer":
        self.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.stop()

    # -------------------------------------------------------------- metricas

    @property
    def startup_seconds(self) -> float | None:
        if self.started_at is None or self.ready_at is None:
            return None
        return self.ready_at - self.started_at

    def _proc_status(self) -> dict[str, str]:
        if self.process is None or self.process.pid is None:
            return {}
        try:
            with open(f"/proc/{self.process.pid}/status", "r", encoding="utf-8") as file:
                fields = {}
                for line in file:
                    key, _, value = line.partition(":")
                    fields[key.strip()] = value.strip()
                return fields
        except OSError:
            return {}

    def rss_mb(self) -> float | None:
        """Memoria residente atual do processo, em MB."""
        value = self._proc_status().get("VmRSS", "")
        return int(value.split()[0]) / 1024 if value.split() else None

    def peak_rss_mb(self) -> float | None:
        """Pico de memoria residente (VmHWM), em MB."""
        value = self._proc_status().get("VmHWM", "")
        return int(value.split()[0]) / 1024 if value.split() else None

    # -------------------------------------------------------------- slots

    def _slot_request(self, action: str, filename: str) -> dict[str, Any]:
        body = json.dumps({"filename": filename}).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/slots/0?action={action}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:200]
            return {"error": f"HTTP {exc.code}: {detail}"}
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            return {"error": str(exc)}

    def save_slot(self, filename: str) -> bool:
        """Salva o cache de contexto do slot 0 (retomada instantanea)."""
        return "error" not in self._slot_request("save", filename)

    def restore_slot(self, filename: str) -> bool:
        """Restaura um cache de contexto salvo anteriormente."""
        return "error" not in self._slot_request("restore", filename)

    # ------------------------------------------------------------------ logs

    def _log_tail(self, lines: int = 15) -> str:
        if self.log_path is None or not self.log_path.is_file():
            return "(sem log; use --log para registrar a saida do servidor)"
        content = self.log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(f"  {line}" for line in content[-lines:])
