from __future__ import annotations

from click.testing import CliRunner

from tishift_mssql.cli import main


def test_main_help_lists_commands() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "scan" in result.output
    assert "convert" in result.output
    assert "load" in result.output
    assert "sync" in result.output
    assert "check" in result.output
