import json
import os
import subprocess
from pathlib import Path

import pytest

from uncredit import cli, remotes


def git(path, *args):
    return subprocess.run(
        ["git", "-C", str(path), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout


@pytest.fixture
def remote(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    source, bare = tmp_path / "source", tmp_path / "remote.git"
    source.mkdir()
    git(source, "init", "-q", "-b", "main")
    git(source, "config", "user.name", "Test User")
    git(source, "config", "user.email", "user@example.com")
    git(source, "commit", "-q", "--allow-empty", "-m", "initial")
    git(source, "checkout", "-q", "-b", "other")
    git(
        source,
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "second\n\nCo-authored-by: Claude <noreply@anthropic.com>",
    )
    git(source, "checkout", "-q", "main")
    git(source, "clone", "-q", "--bare", str(source), str(bare))
    return bare


def test_remote_scan_covers_other_branches_and_removes_its_clone(remote, monkeypatch, capsys):
    before = git(remote, "show-ref")
    original = cli.scan
    visited = []

    def observe(path, me):
        visited.append(path)
        assert git(path, "rev-parse", "--is-bare-repository").strip() == "true"
        assert not (path / ".git").exists()
        return original(path, me)

    monkeypatch.setattr(cli, "scan", observe)
    assert cli.main(["scan", remote.as_uri(), "--me", "user@example.com"]) == 0
    captured = capsys.readouterr()
    assert remote.as_uri() in captured.out
    assert "2 commits; trailers 1" in captured.out
    assert "[1/1] scanning" in captured.err
    assert visited and all(not path.parent.exists() for path in visited)
    assert git(remote, "show-ref") == before


@pytest.mark.parametrize("failure", [RuntimeError("scan failed"), KeyboardInterrupt()])
def test_error_or_interrupt_removes_the_temporary_clone(remote, monkeypatch, failure, capsys):
    visited = []

    def fail(path, me):
        visited.append(path)
        raise failure

    monkeypatch.setattr(cli, "scan", fail)
    if isinstance(failure, KeyboardInterrupt):
        with pytest.raises(KeyboardInterrupt):
            cli.main(["scan", remote.as_uri()])
    else:
        assert cli.main(["scan", remote.as_uri()]) == 1
        assert "scan failed" in capsys.readouterr().err
    assert all(not path.parent.exists() for path in visited)


def test_clone_failure_reports_authentication_and_cleans_temp(tmp_path, monkeypatch, capsys):
    actual = remotes.tempfile.TemporaryDirectory
    folders = []

    def record(**kwargs):
        folder = actual(**kwargs)
        folders.append(Path(folder.name))
        return folder

    monkeypatch.setattr(remotes.tempfile, "TemporaryDirectory", record)
    assert cli.main(["scan", (tmp_path / "missing.git").as_uri()]) == 1
    assert "git authentication" in capsys.readouterr().err
    assert folders and all(not path.exists() for path in folders)


def test_scan_keeps_history_when_remote_head_is_unborn(remote, capsys):
    git(remote, "symbolic-ref", "HEAD", "refs/heads/not-created")
    assert cli.main(["scan", remote.as_uri(), "--me", "user@example.com"]) == 0
    assert "2 commits; trailers 1" in capsys.readouterr().out


def test_clone_interrupt_stops_git_before_temp_cleanup(monkeypatch):
    events = []

    class Process:
        def communicate(self):
            events.append("communicate")
            if len(events) == 1:
                raise KeyboardInterrupt
            return b"", b""

        def kill(self):
            events.append("kill")

    monkeypatch.setattr(remotes.subprocess, "Popen", lambda *a, **kw: Process())
    with pytest.raises(KeyboardInterrupt), remotes.clone("file:///unused"):
        pytest.fail("clone did not stop")
    assert events == ["communicate", "kill", "communicate"]


def test_github_filter_flags_and_fake_gh(remote, monkeypatch, capsys):
    real_run = subprocess.run
    calls = []

    def fake_gh(args, **kwargs):
        if args[0] != "gh":
            return real_run(args, **kwargs)
        calls.append(args)
        return subprocess.CompletedProcess(
            args,
            0,
            json.dumps(
                [
                    {"url": remote.as_uri(), "isFork": False, "isArchived": False},
                    {"url": remote.as_uri() + "?fork", "isFork": True, "isArchived": False},
                    {"url": remote.as_uri() + "?archived", "isFork": False, "isArchived": True},
                ]
            ),
            "",
        )

    monkeypatch.setattr(remotes.subprocess, "run", fake_gh)
    assert cli.main(["scan", "--github", "example"]) == 0
    assert len(calls) == 1 and calls[0][:4] == ["gh", "repo", "list", "example"]
    assert capsys.readouterr().err.count("scanning") == 1
    urls = remotes.github_repos("example", True, True)
    assert len(urls) == 3
    assert len(remotes.github_repos("example", True, False)) == 2
    assert len(remotes.github_repos("example", False, True)) == 2


def test_github_failure_is_visible(monkeypatch, capsys):
    monkeypatch.setattr(
        remotes.subprocess,
        "run",
        lambda args, **kwargs: subprocess.CompletedProcess(args, 1, "", "authentication required"),
    )
    assert cli.main(["scan", "--github", "example"]) == 1
    assert "gh auth status" in capsys.readouterr().err


def test_clean_url_only_prints_commands_without_cloning(monkeypatch, capsys):
    monkeypatch.setattr(remotes, "clone", lambda *a: pytest.fail("remote clone in clean"))
    monkeypatch.setattr(cli, "find_repos", lambda *a: pytest.fail("local clean was attempted"))
    assert cli.main(["clean", "example/project", "--yes", "--push"]) == 0
    output = capsys.readouterr().out
    assert "https://github.com/example/project.git" in output
    assert "clone" in output and "uncredit" in output and "--push" in output
    assert len(output.splitlines()) == 4
    if os.name == "nt":
        assert output.splitlines()[1].startswith("& 'git'")


def test_shorthand_and_existing_local_path_are_distinct(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert remotes.remote_url("example/project") == "https://github.com/example/project.git"
    assert remotes.remote_url("example/project.git") == "https://github.com/example/project.git"
    (tmp_path / "example" / "project").mkdir(parents=True)
    assert remotes.remote_url("example/project") is None
    assert (
        remotes.remote_url("git@example.com:example/project.git")
        == "git@example.com:example/project.git"
    )
