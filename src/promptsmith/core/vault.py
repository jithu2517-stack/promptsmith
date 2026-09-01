from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any, cast

import yaml

from promptsmith.models.types import Prompt, TestCase

VAULT_DIR = ".promptsmith"
PROMPTS_DIR = "prompts"
TESTS_DIR = "tests"
CONFIG_FILE = "config.yaml"
INDEX_FILE = "index.json"


class VaultError(Exception):
    pass


class Vault:
    """Manages the prompt vault — a directory of versioned prompts and test cases."""

    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            root = self._find_vault_root()
        self.root = Path(root) / VAULT_DIR
        self.prompts_path = self.root / PROMPTS_DIR
        self.tests_path = self.root / TESTS_DIR
        self.config_path = self.root / CONFIG_FILE
        self.index_path = self.root / INDEX_FILE

    @staticmethod
    def _find_vault_root() -> Path:
        """Walk up from cwd to find .promptsmith directory."""
        current = Path.cwd()
        for parent in [current, *current.parents]:
            if (parent / VAULT_DIR).is_dir():
                return parent
        return current

    def init(self, force: bool = False) -> None:
        if self.root.exists() and not force:
            raise VaultError(f"Vault already exists at {self.root}. Use --force to reinitialize.")
        self.root.mkdir(parents=True, exist_ok=True)
        self.prompts_path.mkdir(exist_ok=True)
        self.tests_path.mkdir(exist_ok=True)
        if not self.config_path.exists() or force:
            default_config = {
                "version": 1,
                "default_provider": "mock",
                "default_model": "mock",
                "created_at": time.time(),
            }
            with open(self.config_path, "w") as f:
                yaml.dump(default_config, f, default_flow_style=False)
        self._save_index({})

    def get_config(self) -> dict[str, Any]:
        if not self.config_path.exists():
            return {}
        with open(self.config_path) as f:
            config = yaml.safe_load(f)
        return config if isinstance(config, dict) else {}

    def set_config(self, key: str, value: Any) -> None:
        config = self.get_config()
        config[key] = value
        with open(self.config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)

    def _load_index(self) -> dict[str, Any]:
        if not self.index_path.exists():
            return {}
        with open(self.index_path) as f:
            index = json.load(f)
        if not isinstance(index, dict):
            raise VaultError(f"Invalid vault index: {self.index_path}")
        return cast(dict[str, Any], index)

    def _save_index(self, index: dict[str, Any]) -> None:
        with open(self.index_path, "w") as f:
            json.dump(index, f, indent=2, default=str)

    def save_prompt(self, prompt: Prompt, increment_version: bool = True) -> Prompt:
        self.prompts_path.mkdir(parents=True, exist_ok=True)
        index = self._load_index()

        if prompt.name in index and increment_version:
            prompt.version = index[prompt.name]["versions"][-1]["version"] + 1

        prompt_dir = self.prompts_path / prompt.name
        prompt_dir.mkdir(exist_ok=True)
        file_path = prompt_dir / f"v{prompt.version:03d}.yaml"

        if file_path.exists():
            raise VaultError(
                f"Version {prompt.version} of '{prompt.name}' already exists. "
                "Bump the version or use a different name."
            )

        prompt.created_at = time.time()
        prompt.hash = prompt.compute_hash()

        with open(file_path, "w") as f:
            yaml.dump(prompt.to_dict(), f, default_flow_style=False)

        if prompt.name not in index:
            index[prompt.name] = {"versions": [], "latest_version": 0}

        index[prompt.name]["versions"].append(
            {"version": prompt.version, "hash": prompt.hash, "path": str(file_path)}
        )
        index[prompt.name]["latest_version"] = prompt.version
        self._save_index(index)

        return prompt

    def get_prompt(self, name: str, version: int | None = None) -> Prompt | None:
        index = self._load_index()
        if name not in index:
            return None

        entry = index[name]
        if version is None:
            version = entry["latest_version"]

        for v in entry["versions"]:
            if v["version"] == version:
                file_path = Path(v["path"])
                if not file_path.exists():
                    raise VaultError(f"Prompt file missing: {file_path}")
                with open(file_path) as f:
                    data = yaml.safe_load(f)
                if not isinstance(data, dict):
                    raise VaultError(f"Invalid prompt file: {file_path}")
                return Prompt.from_dict(data)

        return None

    def list_prompts(self) -> list[dict[str, Any]]:
        index = self._load_index()
        result = []
        for name, entry in index.items():
            latest = entry["versions"][-1] if entry["versions"] else None
            prompt = self.get_prompt(name) if latest else None
            result.append(
                {
                    "name": name,
                    "latest_version": entry["latest_version"],
                    "total_versions": len(entry["versions"]),
                    "hash": latest["hash"] if latest else "",
                    "description": prompt.description if prompt else "",
                    "tags": prompt.tags if prompt else [],
                }
            )
        return result

    def list_versions(self, name: str) -> list[dict[str, Any]]:
        index = self._load_index()
        if name not in index:
            raise VaultError(f"Prompt '{name}' not found.")
        return cast(list[dict[str, Any]], index[name]["versions"])

    def diff_prompts(self, name: str, v1: int, v2: int) -> dict[str, Any]:
        p1 = self.get_prompt(name, v1)
        p2 = self.get_prompt(name, v2)
        if not p1 or not p2:
            raise VaultError(f"Could not load prompt '{name}' versions {v1} and {v2}.")

        diffs = []
        max_len = max(len(p1.messages), len(p2.messages))
        for i in range(max_len):
            m1 = p1.messages[i] if i < len(p1.messages) else None
            m2 = p2.messages[i] if i < len(p2.messages) else None
            if m1 is None:
                assert m2 is not None
                diffs.append({"type": "added", "index": i, "content": m2.content})
            elif m2 is None:
                diffs.append({"type": "removed", "index": i, "content": m1.content})
            elif m1.content != m2.content or m1.role != m2.role:
                diffs.append(
                    {
                        "type": "changed",
                        "index": i,
                        "old_role": m1.role.value,
                        "new_role": m2.role.value,
                        "old_content": m1.content,
                        "new_content": m2.content,
                    }
                )

        return {
            "prompt_name": name,
            "version_old": v1,
            "version_new": v2,
            "hash_old": p1.hash,
            "hash_new": p2.hash,
            "diffs": diffs,
        }

    def delete_prompt(self, name: str) -> None:
        index = self._load_index()
        if name not in index:
            raise VaultError(f"Prompt '{name}' not found.")
        prompt_dir = self.prompts_path / name
        if prompt_dir.exists():
            shutil.rmtree(prompt_dir)
        del index[name]
        self._save_index(index)

    def export_prompt(self, name: str, output_path: str, version: int | None = None) -> str:
        prompt = self.get_prompt(name, version)
        if not prompt:
            raise VaultError(f"Prompt '{name}' not found.")
        out = Path(output_path)
        with open(out, "w") as f:
            yaml.dump(prompt.to_dict(), f, default_flow_style=False)
        return str(out.resolve())

    def import_prompt(self, file_path: str) -> Prompt:
        with open(file_path) as f:
            data = yaml.safe_load(f)
        prompt = Prompt.from_dict(data)
        prompt.version = 1
        return self.save_prompt(prompt, increment_version=False)

    def save_test(self, test: TestCase) -> None:
        self.tests_path.mkdir(parents=True, exist_ok=True)
        file_path = self.tests_path / f"{test.name}.yaml"
        with open(file_path, "w") as f:
            yaml.dump(test.to_dict(), f, default_flow_style=False)

    def get_test(self, name: str) -> TestCase | None:
        file_path = self.tests_path / f"{name}.yaml"
        if not file_path.exists():
            return None
        with open(file_path) as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise VaultError(f"Invalid test file: {file_path}")
        return TestCase.from_dict(data)

    def list_tests(self) -> list[str]:
        if not self.tests_path.exists():
            return []
        return sorted(
            [f.stem for f in self.tests_path.glob("*.yaml")]
        )
