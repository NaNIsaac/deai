import importlib.util
from pathlib import Path

from uncredit import cli


def test_notice_package_delegates_without_a_second_notice(monkeypatch, capsys):
    path = Path(__file__).parents[1] / "legacy/git-deai/src/git_deai_legacy/__init__.py"
    spec = importlib.util.spec_from_file_location("legacy_entry", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(cli, "main", lambda: 7)
    assert module.main() == 7
    assert capsys.readouterr().err == "deai is now uncredit\n"
