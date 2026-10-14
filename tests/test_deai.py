"""End-to-end check on a throwaway repository: python tests/test_deai.py (or pytest)."""

import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from deai.cli import clean, clean_message, scan  # noqa: E402


def git(repo, *args, env=None):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True,
                          encoding="utf-8", env=env).stdout


def test_messages():
    msg = ("Fix the solver\n\nBody.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n"
           "Co-authored-by: Jane Doe <jane@uni.kr>\n")
    assert clean_message(msg) == "Fix the solver\n\nBody.\n\nCo-authored-by: Jane Doe <jane@uni.kr>\n"
    pr = "Summary\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)\n"
    assert clean_message(pr) == "Summary\n"
    human = "Generated with numpy, by hand\n"
    assert clean_message(human) == human            # "generated with" alone is not an AI credit


def test_rewrite():
    import os
    with tempfile.TemporaryDirectory() as d:
        repo = Path(d)
        git(repo, "init", "-q", "-b", "main")
        git(repo, "config", "user.name", "Isaac Yong")
        git(repo, "config", "user.email", "isaac@example.com")
        (repo / "a.txt").write_text("one\n")
        git(repo, "add", "a.txt")
        git(repo, "commit", "-q", "-m", "first\n\nCo-Authored-By: Claude <noreply@anthropic.com>")
        (repo / "a.txt").write_text("two\n")
        git(repo, "commit", "-q", "-am", "second\n\nCo-authored-by: Jane Doe <jane@uni.kr>")
        env = dict(os.environ, GIT_AUTHOR_NAME="Claude", GIT_AUTHOR_EMAIL="noreply@anthropic.com")
        (repo / "a.txt").write_text("three\n")
        git(repo, "commit", "-q", "-am", "third", env=env)
        git(repo, "tag", "v1")
        tree = git(repo, "rev-parse", "HEAD^{tree}")

        r = scan(repo)
        assert r.commits == 3 and len(r.trailers) == 1 and len(r.idents) == 1, r

        assert clean(repo, None, push=False) == 2
        assert not scan(repo).dirty
        log = git(repo, "log", "--format=%an <%ae>|%B%x1e")
        assert "anthropic" not in log.lower() and "claude" not in log.lower()
        assert "Jane Doe" in log                       # human co-author kept
        assert git(repo, "rev-parse", "HEAD^{tree}") == tree   # content untouched
        assert git(repo, "rev-parse", "v1") == git(repo, "rev-parse", "HEAD")  # tag moved along
        assert list((repo / ".git").glob("deai-backup-*.bundle"))
        assert not git(repo, "status", "--porcelain")


def test_push_never_loses_remote_commits():
    """A local branch behind its remote must be fast-forwarded, not force-pushed backward."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        git(d, "init", "-q", "--bare", "-b", "main", "remote.git")
        for name in ("a", "b"):
            git(d, "clone", "-q", str(d / "remote.git"), name)
            git(d / name, "config", "user.name", "Isaac Yong")
            git(d / name, "config", "user.email", "isaac@example.com")
        a, b = d / "a", d / "b"
        (a / "f").write_text("1\n")
        git(a, "add", "f")
        git(a, "commit", "-q", "-m", "one\n\nCo-Authored-By: Claude <noreply@anthropic.com>")
        git(a, "push", "-q", "origin", "main")
        git(b, "pull", "-q", "origin", "main")       # b moves ahead; a stays behind
        (b / "f").write_text("2\n")
        git(b, "commit", "-q", "-am", "two (only on the remote)")
        git(b, "push", "-q", "origin", "main")

        assert clean(a, None, push=True) == 1
        remote_log = git(d / "remote.git", "log", "--format=%s%n%b", "main")
        assert "two (only on the remote)" in remote_log, remote_log   # not thrown away
        assert "anthropic" not in remote_log.lower()

        (b / "f").write_text("3\n")                  # diverge: b has stale history + a new commit
        git(b, "commit", "-q", "-am", "three\n\nCo-Authored-By: Claude <noreply@anthropic.com>")
        try:
            clean(b, None, push=True)
        except RuntimeError as e:
            assert "diverged" in str(e)
        else:
            raise AssertionError("a diverged branch must stop the run")


if __name__ == "__main__":
    test_messages()
    test_rewrite()
    test_push_never_loses_remote_commits()
    print("deai: all checks passed")
