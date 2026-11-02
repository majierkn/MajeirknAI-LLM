#!/usr/bin/env python3
"""Majeirkn AI: conversa local com um modelo GGUF servido pelo llama-server.

Uso basico:

    python main.py                 # retoma a conversa mais recente (ou cria uma)
    python main.py --new           # comeca uma conversa nova
    python main.py --resume <id>   # retoma uma conversa especifica
    python main.py --web           # interface web no navegador (recomendado no celular)
    python main.py --bench         # mede velocidade e memoria (nao conversa)
    python main.py --attach        # usa um llama-server que ja esta rodando
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

from majeirkn import __version__, bench as bench_mod
from majeirkn import config as config_mod
from majeirkn.client import ChatClient
from majeirkn.history import SessionStore
from majeirkn.repl import Repl
from majeirkn.server import LlamaServer, ServerError, find_llama_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="majeirkn",
        description="Assistente local em portugues do Brasil usando llama.cpp.",
    )
    parser.add_argument("--config", type=Path, default=None,
                        help="caminho do config.json (padrao: o do projeto)")
    parser.add_argument("--new", action="store_true",
                        help="comeca uma conversa nova em vez de retomar a ultima")
    parser.add_argument("--resume", metavar="ID", default=None,
                        help="retoma uma conversa salva (use 'latest' para a mais recente)")
    parser.add_argument("--attach", action="store_true",
                        help="usa um llama-server ja em execucao, sem iniciar outro")
    parser.add_argument("--web", action="store_true",
                        help="serve a interface web e abre o navegador (em vez do terminal)")
    parser.add_argument("--ui-dir", type=Path, default=None,
                        help="diretorio dos arquivos da interface web")
    parser.add_argument("--no-browser", action="store_true",
                        help="com --web, nao tenta abrir o navegador automaticamente")
    parser.add_argument("--log", type=Path, default=None,
                        help="arquivo para registrar a saida do llama-server")
    parser.add_argument("--bench", action="store_true",
                        help="mede carga, velocidade e RAM e sai")
    parser.add_argument("--variants", default=None,
                        help="variantes do benchmark separadas por virgula")
    parser.add_argument("--max-tokens", type=int, default=96,
                        help="tokens por pedicao no benchmark (padrao: 96)")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def prepare_session(store: SessionStore, args: argparse.Namespace, model_name: str):
    """Cria ou carrega a sessao conforme os argumentos."""
    if args.new:
        return store.create(title="Nova conversa", model=model_name), False

    if args.resume:
        target = None if args.resume == "latest" else args.resume
        try:
            session = store.load(target) if target else store.latest()
        except KeyError as exc:
            raise ConfigExit(exc.args[0])
        if session is None:
            raise ConfigExit(f"Nenhuma conversa encontrada para retomar: {args.resume}")
        return session, True

    session = store.latest()
    if session is not None:
        return session, True
    return store.create(title="Nova conversa", model=model_name), False


class ConfigExit(Exception):
    """Erro que deve apenas imprimir a mensagem e sair com codigo 2."""


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        config = config_mod.load_config(args.config)
    except config_mod.ConfigError as exc:
        print(f"[Majeirkn AI] {exc}", file=sys.stderr)
        return 2

    model_path = config_mod.resolve_model_path(config)
    if not model_path.is_file():
        print("[Majeirkn AI] Modelo GGUF nao encontrado.", file=sys.stderr)
        print(f"Caminho esperado: {model_path}", file=sys.stderr)
        print("Execute: bash scripts/download_model.sh", file=sys.stderr)
        return 2

    if args.bench:
        variants = args.variants.split(",") if args.variants else None
        return bench_mod.main(args.config, variants, args.max_tokens)

    data_dir = config_mod.data_dir(config)
    store = SessionStore(data_dir / "sessions")

    try:
        session, resumed = prepare_session(store, args, model_path.name)
    except ConfigExit as exc:
        print(f"[Majeirkn AI] {exc}", file=sys.stderr)
        return 2

    # Diretorio da interface web (pagina propria do projeto).
    ui_dir = (args.ui_dir or config_mod.ROOT / "majeirkn" / "ui").resolve()
    web_mode = bool(args.web)

    llama_server = find_llama_server()
    if llama_server is None and not args.attach:
        print("[Majeirkn AI] llama-server nao encontrado.", file=sys.stderr)
        print("Execute: bash scripts/install_termux.sh", file=sys.stderr)
        print("Ou, se compilou em outro lugar:", file=sys.stderr)
        print("  export LLAMA_SERVER=/caminho/para/llama-server", file=sys.stderr)
        return 2

    warning = config_mod.memory_warning(config, model_path)
    if warning:
        print(f"[Majeirkn AI] Atencao: {warning}", file=sys.stderr)

    server: LlamaServer | None = None
    if not args.attach:
        try:
            server = LlamaServer(
                config,
                model_path,
                llama_server,
                log_path=args.log or (data_dir / "logs" / "server.log"),
                public_path=ui_dir if (web_mode and config["web_ui"] == "majeirkn") else None,
            )
        except ServerError as exc:
            print(f"[Majeirkn AI] {exc}", file=sys.stderr)
            return 2
        if web_mode and config["web_ui"] == "majeirkn" and not (ui_dir / "index.html").is_file():
            print(f"[Majeirkn AI] Interface web nao encontrada em {ui_dir}", file=sys.stderr)
            return 2
        try:
            server.start()
        except ServerError as exc:
            print(f"[Majeirkn AI] {exc}", file=sys.stderr)
            return 1
        print(f"Servidor pronto em {server.base_url}")
        if server.startup_seconds is not None:
            print(f"Modelo carregado em {server.startup_seconds:.1f}s")

    if server is not None:
        client = ChatClient(server.base_url)
        session_server = server
    else:
        client = ChatClient(f"http://{config['host']}:{config['port']}")
        session_server = _AttachedServer(config)
    if not client.health():
        where = client.base_url
        print(f"[Majeirkn AI] Nenhum llama-server respondendo em {where}", file=sys.stderr)
        if server is not None:
            server.stop()
        return 1

    try:
        if web_mode:
            return run_web(client, args)
        repl = Repl(config, session_server, client, store, session)
        if resumed:
            repl.resume_current()
        return repl.run()
    finally:
        if server is not None:
            server.stop()


def run_web(client: ChatClient, args: argparse.Namespace) -> int:
    """Modo --web: mostra o endereco, abre o navegador e espera o Ctrl+C."""
    url = client.base_url + "/"
    print(f"\nMajeirkn AI na web: {url}")
    print("No navegador do celular, abra esse endereco.")
    print("Para instalar como aplicativo: menu do Chrome > Adicionar a tela inicial.")
    print("Ctrl+C encerra o servidor.\n", flush=True)

    if not args.no_browser:
        open_browser(url)

    try:
        while True:
            time.sleep(1.0)
            if not client.health():
                print("[Majeirkn AI] O servidor parou de responder.", file=sys.stderr)
                return 1
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
        return 0


def open_browser(url: str) -> None:
    """Tenta abrir o navegador no Termux; silencioso se nao estiver disponivel."""
    launcher = shutil.which("termux-open-url")
    if launcher is None:
        return
    try:
        subprocess.run([launcher, url], check=False, timeout=10)
    except (OSError, subprocess.SubprocessError):
        pass


class _AttachedServer:
    """Fachada minima para quando o servidor e externo (modo --attach)."""

    def __init__(self, config: dict) -> None:
        self.config = config

    def rss_mb(self):
        return None

    def save_slot(self, filename: str) -> bool:
        return False

    def restore_slot(self, filename: str) -> bool:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
