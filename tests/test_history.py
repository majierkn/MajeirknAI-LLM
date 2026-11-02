"""Testes do armazenamento de sessoes em JSON."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from majeirkn.history import Session, SessionStore


class SessionStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name) / "sessions"
        self.store = SessionStore(self.directory)

    def test_roundtrip(self) -> None:
        session = self.store.create(title="Primeira conversa", model="qwen.gguf")
        session.messages.append({"role": "user", "content": "Ola"})
        session.messages.append({"role": "assistant", "content": "Oi!"})
        self.store.save(session)

        loaded = self.store.load(session.id)
        self.assertEqual(loaded.title, "Primeira conversa")
        self.assertEqual(loaded.messages[0]["content"], "Ola")

    def test_load_missing_raises(self) -> None:
        with self.assertRaises(KeyError):
            self.store.load("nao-existe")

    def test_list_orders_newest_first(self) -> None:
        first = self.store.create(title="A")
        self.store.save(first)
        second = self.store.create(title="B")
        self.store.save(second)
        ids = [session.id for session in self.store.list()]
        self.assertEqual(ids[0], second.id)

    def test_corrupted_files_are_skipped(self) -> None:
        session = self.store.create()
        self.store.save(session)
        (self.directory / "20200101-000000-corrompido.json").write_text(
            "{ quebrado", encoding="utf-8"
        )
        self.assertEqual([s.id for s in self.store.list()], [session.id])

    def test_latest_returns_none_when_empty(self) -> None:
        self.assertIsNone(self.store.latest())

    def test_delete_missing_raises(self) -> None:
        with self.assertRaises(KeyError):
            self.store.delete("nao-existe")

    def test_from_dict_ignores_unknown_fields(self) -> None:
        data = {
            "id": "x", "title": "t", "messages": [{"role": "user", "content": "oi"}],
            "futuro_campo": "ignorado",
        }
        session = Session.from_dict(data)
        self.assertFalse(hasattr(session, "futuro_campo"))
        self.assertEqual(session.slot_file, None)

    def test_from_dict_stringifies_message_content(self) -> None:
        data = {"id": "x", "messages": [{"role": "user", "content": 42}]}
        session = Session.from_dict(data)
        self.assertEqual(session.messages[0]["content"], "42")

    def test_export_markdown_and_text(self) -> None:
        session = self.store.create(title="Conversa", model="qwen.gguf")
        session.messages.append({"role": "user", "content": "Pergunta"})
        session.messages.append({"role": "assistant", "content": "Resposta"})

        md_path = self.store.export(session, Path(self.tmp.name) / "saida.md")
        md = md_path.read_text(encoding="utf-8")
        self.assertIn("# Conversa", md)
        self.assertIn("## Voce", md)
        self.assertIn("Resposta", md)

        txt_path = self.store.export(
            session, Path(self.tmp.name) / "saida.txt", fmt="txt"
        )
        txt = txt_path.read_text(encoding="utf-8")
        self.assertIn("[Voce]", txt)
        self.assertNotIn("## Voce", txt)

    def test_save_is_atomic_after_crash(self) -> None:
        session = self.store.create()
        self.store.save(session)
        # O arquivo temporario nao deve sobrar depois do replace.
        leftovers = list(self.directory.glob("*.tmp"))
        self.assertEqual(leftovers, [])


class SessionTitleTest(unittest.TestCase):
    def test_ids_are_unique_even_in_the_same_second(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp))
            sessions = [store.create(title="Mesma") for _ in range(3)]
            for session in sessions:
                store.save(session)
            ids = [session.id for session in sessions]
            self.assertEqual(len(set(ids)), 3)
            self.assertEqual(len(store.list()), 3)


if __name__ == "__main__":
    unittest.main()
