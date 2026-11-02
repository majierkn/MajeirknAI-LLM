"""Testes de carregamento e validacao do config.json."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from majeirkn import config as config_mod


class LoadConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "config.json"
        self.base = {
            "model_path": "modelos/model.gguf",
            "context_size": 2048,
            "temperature": 0.7,
            "top_p": 0.8,
            "repeat_penalty": 1.1,
            "system_prompt": "Voce e a Majeirkn AI.",
        }

    def write(self, data: dict) -> Path:
        self.path.write_text(json.dumps(data), encoding="utf-8")
        return self.path

    def test_loads_and_applies_defaults(self) -> None:
        config = config_mod.load_config(self.write(self.base))
        self.assertEqual(config["top_k"], 40)
        self.assertEqual(config["port"], 8081)
        self.assertEqual(config["flash_attn"], "auto")
        self.assertIsNone(config["threads"])

    def test_config_antigo_continua_valido(self) -> None:
        # O config da v0.1 so tinha estas chaves.
        config = config_mod.load_config(self.write(self.base))
        self.assertEqual(config["model_path"], "modelos/model.gguf")
        self.assertEqual(config["context_size"], 2048)

    def test_missing_required_key_fails(self) -> None:
        del self.base["model_path"]
        with self.assertRaises(config_mod.ConfigError):
            config_mod.load_config(self.write(self.base))

    def test_invalid_json_fails(self) -> None:
        self.path.write_text("{ nao json ", encoding="utf-8")
        with self.assertRaises(config_mod.ConfigError):
            config_mod.load_config(self.path)

    def test_missing_file_fails(self) -> None:
        with self.assertRaises(config_mod.ConfigError):
            config_mod.load_config(Path(self.tmp.name) / "inexistente.json")

    def test_temperature_out_of_range_fails(self) -> None:
        self.base["temperature"] = 3.0
        with self.assertRaises(config_mod.ConfigError):
            config_mod.load_config(self.write(self.base))

    def test_top_p_above_one_fails(self) -> None:
        self.base["top_p"] = 1.5
        with self.assertRaises(config_mod.ConfigError):
            config_mod.load_config(self.write(self.base))

    def test_repeat_penalty_below_one_fails(self) -> None:
        self.base["repeat_penalty"] = 0.8
        with self.assertRaises(config_mod.ConfigError):
            config_mod.load_config(self.write(self.base))

    def test_ubatch_above_batch_fails(self) -> None:
        self.base.update(batch_size=128, ubatch_size=512)
        with self.assertRaises(config_mod.ConfigError):
            config_mod.load_config(self.write(self.base))

    def test_bad_cache_type_fails(self) -> None:
        self.base["cache_type_k"] = "fp16"
        with self.assertRaises(config_mod.ConfigError):
            config_mod.load_config(self.write(self.base))

    def test_port_out_of_range_fails(self) -> None:
        self.base["port"] = 80
        with self.assertRaises(config_mod.ConfigError):
            config_mod.load_config(self.write(self.base))

    def test_bool_is_not_accepted_as_int(self) -> None:
        # bool herda de int em Python e passaria silenciosamente.
        self.base["context_size"] = True
        with self.assertRaises(config_mod.ConfigError):
            config_mod.load_config(self.write(self.base))

    def test_threads_null_means_auto(self) -> None:
        config = config_mod.load_config(self.write(self.base))
        self.assertGreaterEqual(config_mod.resolve_threads(config), 1)

    def test_threads_explicit_is_respected(self) -> None:
        self.base["threads"] = 3
        config = config_mod.load_config(self.write(self.base))
        self.assertEqual(config_mod.resolve_threads(config), 3)

    def test_data_dir_env_override(self) -> None:
        config = config_mod.load_config(self.write(self.base))
        custom = Path(self.tmp.name) / "home-majeirkn"
        previous = os.environ.get("MAJEIRKN_HOME")
        os.environ["MAJEIRKN_HOME"] = str(custom)
        try:
            self.assertEqual(config_mod.data_dir(config), custom)
            self.assertTrue(custom.is_dir())
        finally:
            if previous is None:
                os.environ.pop("MAJEIRKN_HOME", None)
            else:
                os.environ["MAJEIRKN_HOME"] = previous

    def test_memory_warning_without_model_is_silent(self) -> None:
        config = config_mod.load_config(self.write(self.base))
        self.assertIsNone(config_mod.memory_warning(config, Path("/nao/existe.gguf")))


if __name__ == "__main__":
    unittest.main()
