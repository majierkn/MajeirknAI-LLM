"""Sessoes de conversa salvas em disco (JSON) e exportacao para texto."""
from __future__ import annotations

import json
import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _slugify(text: str, limit: int = 40) -> str:
    """Transforma o titulo em nome de arquivo seguro."""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    return cleaned[:limit] or "conversa"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Session:
    """Uma conversa: metadados + lista de mensagens no formato OpenAI."""

    id: str
    title: str = "Nova conversa"
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    model: str = ""
    messages: list[dict[str, str]] = field(default_factory=list)
    slot_file: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "model": self.model,
            "slot_file": self.slot_file,
            "messages": self.messages,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        known = {
            "id", "title", "created_at", "updated_at", "model", "messages", "slot_file",
        }
        fields = {key: value for key, value in data.items() if key in known}
        messages = [
            {"role": str(item.get("role", "user")), "content": str(item.get("content", ""))}
            for item in fields.get("messages", [])
            if isinstance(item, dict)
        ]
        fields["messages"] = messages
        fields.setdefault("title", "Nova conversa")
        return cls(**fields)


class SessionStore:
    """Diretorio de sessoes em JSON, uma conversa por arquivo."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------- caminhos

    def _path(self, session_id: str) -> Path:
        return self.directory / f"{session_id}.json"

    def _new_id(self, title: str) -> str:
        # O sufixo aleatorio evita colisao quando duas sessoes nascem no mesmo
        # segundo (o teste de unicidade falharia com o timestamp sozinho).
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        return f"{stamp}-{_slugify(title, limit=24)}-{uuid.uuid4().hex[:4]}"

    # -------------------------------------------------------------- operações

    def create(self, title: str = "Nova conversa", model: str = "") -> Session:
        session = Session(id=self._new_id(title), title=title, model=model)
        return session

    def save(self, session: Session) -> Path:
        session.updated_at = _now_iso()
        path = self._path(session.id)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(session.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        tmp.replace(path)  # evita arquivo corrompido se a escrita for interrompida
        return path

    def load(self, session_id: str) -> Session:
        path = self._path(session_id)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise KeyError(f"Sessao nao encontrada: {session_id}") from exc
        except json.JSONDecodeError as exc:
            raise KeyError(f"Sessao corrompida ({session_id}): {exc}") from exc
        return Session.from_dict(data)

    def list(self) -> list[Session]:
        sessions = []
        for path in sorted(self.directory.glob("*.json"), reverse=True):
            try:
                sessions.append(Session.from_dict(json.loads(path.read_text(encoding="utf-8"))))
            except (json.JSONDecodeError, OSError):
                continue  # ignora arquivos ilegiveis em vez de quebrar a listagem
        return sessions

    def latest(self) -> Session | None:
        sessions = self.list()
        return sessions[0] if sessions else None

    def delete(self, session_id: str) -> None:
        try:
            self._path(session_id).unlink()
        except FileNotFoundError as exc:
            raise KeyError(f"Sessao nao encontrada: {session_id}") from exc

    # -------------------------------------------------------------- exportar

    def export(self, session: Session, destination: Path, fmt: str = "md") -> Path:
        """Escreve a conversa em Markdown ou texto puro."""
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)

        labels = {
            "system": "Sistema", "user": "Voce", "assistant": "Majeirkn AI",
        }
        lines: list[str] = [f"# {session.title}", ""]
        if fmt == "md":
            lines += [
                f"- Modelo: {session.model or 'n/a'}",
                f"- Sessao: {session.id}",
                f"- Atualizada: {session.updated_at}",
                "",
            ]
        for message in session.messages:
            role = labels.get(message["role"], message["role"])
            if fmt == "md":
                lines += [f"## {role}", "", message["content"], ""]
            else:
                lines += [f"[{role}]", message["content"], ""]

        destination.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        return destination
