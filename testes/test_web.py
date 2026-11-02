"""Testes da interface web: comando do servidor, arquivos e PWA."""
from __future__ import annotations

import json
import re
import struct
import tempfile
import unittest
from pathlib import Path

from majeirkn import config as config_mod
from majeirkn.server import LlamaServer, ServerError

ROOT = config_mod.ROOT
UI_DIR = ROOT / "majeirkn" / "ui"


def make_config(**overrides) -> dict:
    config = {
        **config_mod.DEFAULTS,
        "model_path": "modelos/model.gguf",
        "system_prompt": "Voce e a Majeirkn AI.",
        "temperature": 0.7,
        "top_p": 0.8,
        "repeat_penalty": 1.1,
    }
    config.update(overrides)
    return config


def build_command(config: dict, public_path: Path | None = None) -> list[str]:
    server = LlamaServer(config, Path("model.gguf"), Path("llama-server"), public_path=public_path)
    return server.build_command()


class ServerCommandTest(unittest.TestCase):
    def test_public_path_adds_path_flag(self) -> None:
        command = build_command(make_config(), public_path=UI_DIR)
        self.assertIn("--path", command)
        self.assertEqual(command[command.index("--path") + 1], str(UI_DIR))

    def test_no_public_path_omits_flag(self) -> None:
        command = build_command(make_config())
        self.assertNotIn("--path", command)

    def test_oficial_ui_omits_path(self) -> None:
        # A UI embutida do llama.cpp e servida sem --path.
        command = build_command(make_config(web_ui="oficial"), public_path=UI_DIR)
        self.assertNotIn("--path", command)

    def test_missing_ui_dir_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ServerError):
                build_command(make_config(), public_path=Path(tmp) / "nao-existe")

    def test_thinking_disabled_by_default(self) -> None:
        command = build_command(make_config())
        self.assertIn("--reasoning-budget", command)
        self.assertEqual(command[command.index("--reasoning-budget") + 1], "0")

    def test_thinking_enabled_omits_budget(self) -> None:
        command = build_command(make_config(enable_thinking=True))
        self.assertNotIn("--reasoning-budget", command)


class WebUITest(unittest.TestCase):
    """Os arquivos da pagina existem e conversam entre si."""

    def test_core_files_exist(self) -> None:
        for name in ("index.html", "app.js", "style.css", "manifest.json", "sw.js", "system.txt"):
            self.assertTrue((UI_DIR / name).is_file(), f"faltando {name}")

    def test_index_references_every_asset(self) -> None:
        html = (UI_DIR / "index.html").read_text(encoding="utf-8")
        for asset in ("app.js", "style.css", "manifest.json"):
            self.assertIn(asset, html)
        self.assertIn('src="./icons/icon-192.png"', html)

    def test_manifest_icons_exist(self) -> None:
        manifest = json.loads((UI_DIR / "manifest.json").read_text(encoding="utf-8"))
        for icon in manifest["icons"]:
            path = (UI_DIR / icon["src"]).resolve()
            self.assertTrue(path.is_file(), f"icone ausente: {icon['src']}")
            declared = re.match(r"^(\d+)x(\d+)$", icon["sizes"])
            self.assertIsNotNone(declared, f"tamanho invalido: {icon['sizes']}")

    def test_icons_are_valid_pngs_of_declared_size(self) -> None:
        for name, size in (("icon-192.png", 192), ("icon-512.png", 512)):
            data = (UI_DIR / "icons" / name).read_bytes()
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n", f"{name}: assinatura")
            width, height = struct.unpack(">II", data[16:24])
            self.assertEqual((width, height), (size, size))

    def test_sw_covers_the_shell(self) -> None:
        sw = (UI_DIR / "sw.js").read_text(encoding="utf-8")
        for asset in ("./index.html", "./app.js", "./style.css", "./manifest.json"):
            self.assertIn(asset, sw)
        self.assertIn("/v1/", sw, "a API precisa ficar fora do cache")

    def test_app_targets_chat_endpoint(self) -> None:
        js = (UI_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("/v1/chat/completions", js)
        self.assertIn("[DONE]", js)
        self.assertIn("AbortController", js, "o botao Parar precisa abortar a geracao")

    def test_system_prompt_matches_config(self) -> None:
        # system.txt e o prompt do config.json nao podem divergir em silencio.
        config = config_mod.load_config()
        served = (UI_DIR / "system.txt").read_text(encoding="utf-8").strip()
        self.assertEqual(served, config["system_prompt"].strip())

    def test_css_has_mobile_safe_area(self) -> None:
        css = (UI_DIR / "style.css").read_text(encoding="utf-8")
        self.assertIn("safe-area-inset-bottom", css)


class ConfigWebUiTest(unittest.TestCase):
    def test_invalid_web_ui_rejected(self) -> None:
        with self.assertRaises(config_mod.ConfigError):
            config_mod.validate(make_config(web_ui="hacker"))

    def test_valid_web_ui_values(self) -> None:
        for value in ("majeirkn", "oficial", "nenhuma"):
            config_mod.validate(make_config(web_ui=value))


if __name__ == "__main__":
    unittest.main()
