from __future__ import annotations

import json
import os
import tempfile

import pytest

from promptsmith.core.vault import Vault, VaultError
from promptsmith.models.types import Message, Prompt, Role


@pytest.fixture
def temp_vault():
    with tempfile.TemporaryDirectory() as tmp:
        vault = Vault(tmp)
        vault.init()
        yield vault


class TestVault:
    def test_init_creates_structure(self, temp_vault):
        assert temp_vault.root.exists()
        assert temp_vault.prompts_path.exists()
        assert temp_vault.tests_path.exists()
        assert temp_vault.config_path.exists()

    def test_init_twice_raises(self, temp_vault):
        with pytest.raises(VaultError):
            temp_vault.init()

    def test_init_force(self, temp_vault):
        temp_vault.init(force=True)

    def test_save_and_get_prompt(self, temp_vault):
        prompt = Prompt(
            name="test-prompt",
            messages=[
                Message(role=Role.SYSTEM, content="You are helpful."),
                Message(role=Role.USER, content="Hello!"),
            ],
            description="A test prompt",
            tags=["test"],
        )
        saved = temp_vault.save_prompt(prompt)
        assert saved.version == 1
        assert saved.hash
        assert saved.hash == prompt.compute_hash()

        loaded = temp_vault.get_prompt("test-prompt")
        assert loaded is not None
        assert loaded.name == "test-prompt"
        assert len(loaded.messages) == 2
        assert loaded.messages[0].role == Role.SYSTEM
        assert loaded.messages[1].content == "Hello!"

    def test_version_increment(self, temp_vault):
        p1 = Prompt(name="vtest", messages=[Message(Role.USER, "v1")])
        temp_vault.save_prompt(p1)
        assert p1.version == 1

        p2 = Prompt(name="vtest", messages=[Message(Role.USER, "v2")])
        saved = temp_vault.save_prompt(p2)
        assert saved.version == 2

        versions = temp_vault.list_versions("vtest")
        assert len(versions) == 2

    def test_get_nonexistent_prompt(self, temp_vault):
        assert temp_vault.get_prompt("nonexistent") is None

    def test_list_prompts(self, temp_vault):
        p1 = Prompt(name="a", messages=[Message(Role.USER, "hi")])
        p2 = Prompt(name="b", messages=[Message(Role.USER, "hey")])
        temp_vault.save_prompt(p1)
        temp_vault.save_prompt(p2)

        prompts = temp_vault.list_prompts()
        names = {p["name"] for p in prompts}
        assert names == {"a", "b"}

    def test_diff_prompts(self, temp_vault):
        p1 = Prompt(name="diff-test", messages=[Message(Role.USER, "version one")])
        temp_vault.save_prompt(p1)

        p2 = Prompt(name="diff-test", messages=[Message(Role.USER, "version two")])
        temp_vault.save_prompt(p2)

        result = temp_vault.diff_prompts("diff-test", 1, 2)
        assert len(result["diffs"]) > 0
        assert result["diffs"][0]["type"] == "changed"

    def test_diff_no_changes(self, temp_vault):
        p1 = Prompt(name="same", messages=[Message(Role.USER, "same")])
        temp_vault.save_prompt(p1)
        temp_vault.save_prompt(p1)

        result = temp_vault.diff_prompts("same", 1, 2)
        assert len(result["diffs"]) == 0

    def test_delete_prompt(self, temp_vault):
        p = Prompt(name="delme", messages=[Message(Role.USER, "delete")])
        temp_vault.save_prompt(p)
        temp_vault.delete_prompt("delme")
        assert temp_vault.get_prompt("delme") is None

    def test_export_import(self, temp_vault):
        p = Prompt(
            name="export-test",
            messages=[Message(Role.SYSTEM, "system"), Message(Role.USER, "user")],
            description="test export",
            tags=["export"],
        )
        temp_vault.save_prompt(p)

        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as tf:
            export_path = tf.name

        exported = temp_vault.export_prompt("export-test", export_path)
        assert os.path.exists(exported)

        with tempfile.TemporaryDirectory() as tmp2:
            vault2 = Vault(tmp2)
            vault2.init()
            imported = vault2.import_prompt(export_path)
            assert imported.name == "export-test"
            assert len(imported.messages) == 2

    def test_save_test_and_list(self, temp_vault):
        from promptsmith.models.types import TestCase

        tc = TestCase(
            name="test-1",
            description="Check greeting",
            expected_patterns=["hello", "hi"],
            forbidden_patterns=["goodbye"],
        )
        temp_vault.save_test(tc)

        tests = temp_vault.list_tests()
        assert "test-1" in tests

        loaded = temp_vault.get_test("test-1")
        assert loaded is not None
        assert loaded.description == "Check greeting"
        assert "hello" in loaded.expected_patterns

    def test_config(self, temp_vault):
        cfg = temp_vault.get_config()
        assert "version" in cfg

        temp_vault.set_config("default_provider", "openai")
        cfg = temp_vault.get_config()
        assert cfg["default_provider"] == "openai"

    def test_get_config_from_uninitialized(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Vault(tmp)
            assert vault.get_config() == {}


class TestPromptModel:
    def test_hash_consistency(self):
        p1 = Prompt(name="h", messages=[Message(Role.USER, "hello")])
        p2 = Prompt(name="h", messages=[Message(Role.USER, "hello")])
        assert p1.hash == p2.hash

    def test_hash_differs(self):
        p1 = Prompt(name="h", messages=[Message(Role.USER, "hello")])
        p2 = Prompt(name="h", messages=[Message(Role.USER, "world")])
        assert p1.hash != p2.hash

    def test_serialization_roundtrip(self):
        original = Prompt(
            name="serde",
            messages=[
                Message(Role.SYSTEM, "system msg"),
                Message(Role.USER, "user msg"),
            ],
            version=2,
            description="roundtrip",
            tags=["tag1", "tag2"],
            metadata={"key": "value"},
        )
        data = original.to_dict()
        restored = Prompt.from_dict(data)
        assert restored.name == original.name
        assert restored.version == original.version
        assert restored.hash == original.hash
        assert len(restored.messages) == 2
        assert restored.tags == ["tag1", "tag2"]
