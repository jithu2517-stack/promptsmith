from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from promptsmith.cli import main


def test_cli_help() -> None:
    result = CliRunner().invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "Prompt Engineering Toolkit" in result.output


def test_cli_creates_and_runs_mock_prompt(tmp_path: Path) -> None:
    runner = CliRunner()
    vault_dir = str(tmp_path)

    initialized = runner.invoke(main, ["--vault-dir", vault_dir, "init"])
    created = runner.invoke(
        main,
        [
            "--vault-dir",
            vault_dir,
            "create",
            "greeting",
            "--user",
            "Hello {{name}}",
        ],
    )
    executed = runner.invoke(
        main,
        ["--vault-dir", vault_dir, "run", "greeting", "--var", "name=Ada"],
    )

    assert initialized.exit_code == 0
    assert created.exit_code == 0
    assert executed.exit_code == 0
    assert "MOCK RESPONSE" in executed.output
