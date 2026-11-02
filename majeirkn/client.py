"""Cliente HTTP para a API de chat do llama-server (com streaming SSE)."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Iterator

from .server import ServerError


class ChatClient:
    """Fala com um llama-server local pela API /v1/chat/completions."""

    def __init__(self, base_url: str, timeout: float = 900.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ------------------------------------------------------------------http

    def _post(self, path: str, payload: dict[str, Any]) -> tuple[int, Any]:
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise ServerError(f"O servidor respondeu HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise ServerError(f"Falha de conexao com o servidor: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise ServerError(f"Resposta invalida do servidor: {exc}") from exc

    # --------------------------------------------------------------- chat

    def chat_once(self, messages: list[dict[str, str]], params: dict[str, Any]) -> dict[str, Any]:
        """Uma resposta completa, sem streaming: util para testes e benchmark."""
        status, body = self._post(
            "/v1/chat/completions", {"messages": messages, "stream": False, **params}
        )
        if status != 200:
            raise ServerError(f"O servidor respondeu HTTP {status}: {body}")
        choice = (body.get("choices") or [{}])[0].get("message", {})
        return {
            "content": choice.get("content", ""),
            "reasoning": choice.get("reasoning_content", ""),
            "usage": body.get("usage") or {},
            "timings": body.get("timings") or {},
        }

    def chat_stream(
        self, messages: list[dict[str, str]], params: dict[str, Any]
    ) -> Iterator[dict[str, Any]]:
        """Resposta em streaming.

        Gera {"type": "delta", "text": ...} para cada pedaco de texto,
        {"type": "reasoning", "text": ...} quando o modelo pensa em voz alta e,
        no fim, {"type": "done", "usage": ..., "timings": ..., "seconds": ...}.
        """
        payload = {
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
            **params,
        }
        request = urllib.request.Request(
            f"{self.base_url}/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
            method="POST",
        )
        started = time.monotonic()
        try:
            response = urllib.request.urlopen(request, timeout=self.timeout)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise ServerError(f"O servidor respondeu HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise ServerError(f"Falha de conexao com o servidor: {exc.reason}") from exc

        usage: dict[str, Any] = {}
        timings: dict[str, Any] = {}
        try:
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue

                if chunk.get("usage"):
                    usage = chunk["usage"]
                if chunk.get("timings"):
                    timings = chunk["timings"]
                delta = (chunk.get("choices") or [{}])[0].get("delta", {})
                if delta.get("reasoning_content"):
                    yield {"type": "reasoning", "text": delta["reasoning_content"]}
                if delta.get("content"):
                    yield {"type": "delta", "text": delta["content"]}
        finally:
            response.close()

        yield {
            "type": "done",
            "usage": usage,
            "timings": timings,
            "seconds": time.monotonic() - started,
        }

    # -------------------------------------------------------------- extras

    def health(self) -> bool:
        """GET /health; 200 significa pronto para receber requests."""
        try:
            with urllib.request.urlopen(f"{self.base_url}/health", timeout=10) as response:
                return response.status == 200
        except (urllib.error.URLError, OSError):
            return False

    def props(self) -> dict[str, Any]:
        """GET /props: informacoes do modelo e capacidades do servidor."""
        try:
            with urllib.request.urlopen(f"{self.base_url}/props", timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            return {}
