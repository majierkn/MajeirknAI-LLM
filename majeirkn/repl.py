"""Laco de conversa da Majeirkn AI: comandos, streaming e gravacao de sessoes."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from . import config as config_mod
from .client import ChatClient
from .history import Session, SessionStore
from .server import LlamaServer, ServerError

# Parametros que o usuario pode mudar em tempo de execucao com /set
TUNABLES = {
    "temperature": float,
    "top_p": float,
    "top_k": int,
    "min_p": float,
    "repeat_penalty": float,
    "presence_penalty": float,
    "max_tokens": int,
}

HELP_TEXT = """Comandos disponiveis:
  /help              mostra esta lista
  /new [titulo]      comeca uma conversa nova
  /resume [id]       retoma uma conversa (sem id, pega a mais recente)
  /sessions          lista as conversas salvas
  /save              grava a conversa agora (ela ja e salva a cada turno)
  /export [arquivo]  exporta a conversa em Markdown
  /title <texto>     muda o titulo da conversa
  /params            mostra os parametros de amostragem ativos
  /set <chave> <v>   muda um parametro: {keys}
  /model             mostra informacoes do modelo carregado
  /slots             mostra o estado do checkpoint de contexto
  /clear             apaga o historico (mantem as instrucoes do sistema)
  /exit              sai (atalho: Ctrl+C)""".format(keys=", ".join(TUNABLES))


class Repl:
    """Conversa interativa com streaming, comandos e sessao persistente."""

    def __init__(
        self,
        config: dict[str, Any],
        server: LlamaServer,
        client: ChatClient,
        store: SessionStore,
        session: Session,
    ) -> None:
        self.config = config
        self.server = server
        self.client = client
        self.store = store
        self.session = session
        self.params: dict[str, Any] = {
            "temperature": float(config["temperature"]),
            "top_p": float(config["top_p"]),
            "top_k": int(config["top_k"]),
            "min_p": float(config["min_p"]),
            "repeat_penalty": float(config["repeat_penalty"]),
            "max_tokens": int(config["max_tokens"]),
            "cache_prompt": True,
        }
        self.interrupted = False

    # ---------------------------------------------------------------- mensagens

    def _system_message(self) -> dict[str, str]:
        return {"role": "system", "content": self.config["system_prompt"]}

    def _messages(self) -> list[dict[str, str]]:
        return [self._system_message()] + self.session.messages

    def _touch_title(self, text: str) -> None:
        """Usa a primeira pergunta do usuario como titulo, se ainda for o padrao."""
        if self.session.title == "Nova conversa" and text.strip():
            self.session.title = text.strip().splitlines()[0][:50] or "Nova conversa"

    def _save_slot(self) -> None:
        """Grava o cache de contexto para retomar a sessao sem reprocessar tudo."""
        if not self.config.get("use_slot_cache", True):
            return
        filename = f"{self.session.id}.slot"
        if self.server.save_slot(filename):
            self.session.slot_file = filename
        else:
            self.session.slot_file = None

    def ask(self, text: str) -> str:
        """Envia a mensagem do usuario e imprime a resposta em streaming."""
        self.session.messages.append({"role": "user", "content": text})
        parts: list[str] = []
        usage: dict[str, Any] = {}
        timings: dict[str, Any] = {}
        elapsed = 0.0
        self.interrupted = False

        print("Majeirkn AI> ", end="", flush=True)
        try:
            for event in self.client.chat_stream(self._messages(), self.params):
                if event["type"] == "delta":
                    parts.append(event["text"])
                    print(event["text"], end="", flush=True)
                elif event["type"] == "reasoning":
                    continue  # pensamento so existe com enable_thinking ligado
                elif event["type"] == "done":
                    usage = event.get("usage") or {}
                    timings = event.get("timings") or {}
                    elapsed = float(event.get("seconds") or 0.0)
        except KeyboardInterrupt:
            self.interrupted = True
            print("\n(geracao interrompida)", flush=True)
        except ServerError as exc:
            print(f"\nErro: {exc}", file=sys.stderr)
            self.session.messages.pop()  # nao guarda a pergunta que falhou
            self.store.save(self.session)
            return ""
        finally:
            print(flush=True)

        answer = "".join(parts)
        if answer.strip():
            self.session.messages.append({"role": "assistant", "content": answer})

        self._touch_title(text)
        self._save_slot()
        self.store.save(self.session)
        self._print_stats(usage, timings, elapsed)
        return answer

    def _print_stats(self, usage: dict[str, Any], timings: dict[str, Any], elapsed: float) -> None:
        """Linha final com tokens gerados, velocidade e consumo de contexto."""
        prompt_tokens = usage.get("prompt_tokens") or timings.get("prompt_n") or "?"
        completion_tokens = usage.get("completion_tokens") or timings.get("predicted_n") or "?"

        rate = ""
        if timings.get("predicted_per_second"):
            rate = f" a {float(timings['predicted_per_second']):.1f} tok/s"
        elif isinstance(completion_tokens, int) and elapsed > 0:
            rate = f" a {completion_tokens / elapsed:.1f} tok/s"

        rss = self.server.rss_mb()
        rss_text = f", RAM {rss:.0f} MB" if rss else ""
        print(
            f"[{completion_tokens} tokens{rate}, contexto {prompt_tokens}{rss_text}]",
            flush=True,
        )

    # --------------------------------------------------------------- comandos

    def handle(self, line: str) -> bool:
        """Executa um comando; devolve False quando e hora de sair."""
        name, _, rest = line.partition(" ")
        name = name.lower()
        rest = rest.strip()

        if name in {"/exit", "/quit", "/sair"}:
            return False
        if name == "/help":
            print(HELP_TEXT)
        elif name == "/new":
            self.session = self.store.create(title=rest or "Nova conversa", model=self.session.model)
            self.store.save(self.session)
            print(f"Nova conversa: {self.session.id}")
        elif name == "/resume":
            self._resume(rest)
        elif name == "/sessions":
            self._list_sessions()
        elif name == "/save":
            path = self.store.save(self.session)
            print(f"Conversa salva em {path}")
        elif name == "/export":
            self._export(rest)
        elif name == "/title":
            if rest:
                self.session.title = rest
                self.store.save(self.session)
                print(f"Titulo: {rest}")
            else:
                print("Uso: /title <novo titulo>")
        elif name == "/params":
            self._show_params()
        elif name == "/set":
            self._set_param(rest)
        elif name == "/model":
            self._show_model()
        elif name == "/slots":
            state = self.session.slot_file or "(nenhum checkpoint salvo)"
            print(f"Checkpoint de contexto: {state}")
        elif name == "/clear":
            self.session.messages.clear()
            self.store.save(self.session)
            print("Historico apagado. As instrucoes do sistema foram mantidas.")
        else:
            print(f"Comando desconhecido: {name} (use /help)")
        return True

    def _resume(self, rest: str) -> None:
        target = rest or None
        try:
            session = self.store.load(target) if target else self.store.latest()
        except KeyError as exc:
            print(exc.args[0])
            return
        if session is None:
            print("Nenhuma conversa salva encontrada.")
            return

        self.session = session
        self.resume_current()

    def resume_current(self) -> None:
        """Avisa que a sessao foi retomada e restaura o checkpoint de contexto."""
        session = self.session
        turns = sum(1 for message in session.messages if message["role"] == "user")
        print(f"Conversa retomada: {session.id} ({turns} perguntas)")

        # Se existir checkpoint do contexto, restaura para nao reprocessar tudo.
        if session.slot_file and self.config.get("use_slot_cache", True):
            if not self.server.restore_slot(session.slot_file):
                print("Checkpoint incompativel; o contexto sera reprocessado normalmente.")

    def _list_sessions(self) -> None:
        sessions = self.store.list()
        if not sessions:
            print("Nenhuma conversa salva.")
            return
        for session in sessions[:20]:
            turns = sum(1 for message in session.messages if message["role"] == "user")
            marker = ">" if session.id == self.session.id else " "
            print(f"{marker} {session.id}  {turns} perguntas  {session.title}")

    def _export(self, rest: str) -> None:
        if rest:
            destination = Path(rest).expanduser()
            fmt = "txt" if destination.suffix.lower() == ".txt" else "md"
        else:
            # Sem argumento, grava na pasta de dados com nome seguro: o titulo
            # pode conter "?" ou espacos, que o armazenamento compartilhado rejeita.
            destination = (
                config_mod.data_dir(self.config) / "exports" / f"{self.session.id}.md"
            )
            fmt = "md"
        try:
            path = self.store.export(self.session, destination, fmt=fmt)
        except OSError as exc:
            print(f"Falha ao exportar: {exc}")
            return
        print(f"Conversa exportada para {path}")

    def _show_params(self) -> None:
        print("Parametros de amostragem:")
        for key, value in self.params.items():
            if key == "cache_prompt":
                continue
            print(f"  {key} = {value}")

    def _set_param(self, rest: str) -> None:
        key, _, raw = rest.partition(" ")
        key = key.lower()
        raw = raw.strip()
        if key not in TUNABLES:
            print(f"Parametro desconhecido. Use um de: {', '.join(TUNABLES)}")
            return
        try:
            value = TUNABLES[key](raw)
        except ValueError:
            print(f"Valor invalido para {key}: {raw!r}")
            return
        self.params[key] = value
        print(f"{key} = {value}")

    def _show_model(self) -> None:
        props = self.client.props()
        if not props:
            print("Nao foi possivel obter informacoes do servidor.")
            return
        for key in ("model_path", "model_name", "n_ctx", "modalities", "chat_template"):
            if key in props:
                print(f"  {key}: {props[key]}")

    # ------------------------------------------------------------------- loop

    def run(self) -> int:
        """Loop principal; devolve o codigo de saida do programa."""
        print(f"Majeirkn AI - sessao {self.session.id}")
        print("Digite /help para ver os comandos, /exit para sair.\n")
        while True:
            try:
                line = input("voce> ").strip()
            except EOFError:
                print()
                return 0
            except KeyboardInterrupt:
                print()
                return 0
            if not line:
                continue
            if line.startswith("/"):
                if not self.handle(line):
                    self.store.save(self.session)
                    return 0
                continue
            self.ask(line)
