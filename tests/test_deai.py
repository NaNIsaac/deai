"""End-to-end check on a throwaway repository: python tests/test_deai.py (or pytest)."""

import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from deai.cli import clean, clean_message, main, scan, unpushed  # noqa: E402


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

        (b / "f").write_text("3\n")                  # b: stale history + a new commit of its own
        git(b, "commit", "-q", "-am", "three\n\nCo-Authored-By: Claude <noreply@anthropic.com>")
        clean(b, None, push=True)                    # the remote has nothing b lacks: safe to push
        remote_log = git(d / "remote.git", "log", "--format=%s%n%b", "main")
        assert "three" in remote_log and "two (only on the remote)" in remote_log, remote_log
        assert "anthropic" not in remote_log.lower()


def two_clones(d: Path) -> tuple[Path, Path, Path]:
    """A bare remote with one AI-credited commit, cloned twice."""
    git(d, "init", "-q", "--bare", "-b", "main", "remote.git")
    clones = []
    for name in ("a", "b"):
        git(d, "clone", "-q", str(d / "remote.git"), name)
        git(d / name, "config", "user.name", "Isaac Yong")
        git(d / name, "config", "user.email", "isaac@example.com")
        clones.append(d / name)
    a, b = clones
    (a / "f").write_text("1\n")
    git(a, "add", "f")
    git(a, "commit", "-q", "-m", "one\n\nCo-Authored-By: Claude <noreply@anthropic.com>")
    git(a, "push", "-q", "origin", "main")
    git(b, "pull", "-q", "origin", "main")
    return d / "remote.git", a, b


def test_clean_then_push_publishes():
    """`clean` without --push, then `clean --push`, must publish instead of 'nothing to clean'."""
    with tempfile.TemporaryDirectory() as d:
        remote, a, _ = two_clones(Path(d))
        assert main(["clean", str(a), "--yes"]) == 0
        assert unpushed(a) == ["main"]
        assert "anthropic" in git(remote, "log", "--format=%B", "main").lower()
        assert main(["clean", str(a), "--yes", "--push"]) == 0
        assert "anthropic" not in git(remote, "log", "--format=%B", "main").lower()
        assert not unpushed(a)


def test_stale_clone_follows_cleaned_remote():
    """A clone with the old history adopts the remote's rewrite instead of pushing the old one back."""
    with tempfile.TemporaryDirectory() as d:
        remote, a, b = two_clones(Path(d))
        clean(a, None, push=True)
        (a / "f").write_text("2\n")
        git(a, "commit", "-q", "-am", "two (after the cleanup)")
        git(a, "push", "-q", "origin", "main")
        head = git(remote, "rev-parse", "main")
        assert clean(b, None, push=True) == 0          # b only has the old copy of "one"
        assert git(b, "rev-parse", "main") == head == git(remote, "rev-parse", "main")
        assert list((b / ".git").glob("deai-backup-*.bundle"))


def test_work_on_both_sides_stops():
    with tempfile.TemporaryDirectory() as d:
        remote, a, b = two_clones(Path(d))
        clean(a, None, push=True)
        (a / "g").write_text("2\n")
        git(a, "add", "g")
        git(a, "commit", "-q", "-m", "two (remote only)")
        git(a, "push", "-q", "origin", "main")
        (b / "h").write_text("3\n")
        git(b, "add", "h")
        git(b, "commit", "-q", "-m", "three (b only)")
        before = git(remote, "rev-parse", "main")
        try:
            clean(b, None, push=True)
        except RuntimeError as e:
            assert "git rebase origin/main" in str(e) and "git pull" in str(e), e
        else:
            raise AssertionError("work on both sides must stop the run")
        assert git(remote, "rev-parse", "main") == before   # remote untouched
        git(b, "rebase", "-q", "origin/main")                # the advice works: old commit dropped
        assert not scan(b).dirty
        git(b, "push", "-q", "origin", "main")               # a plain fast-forward push now
        log = git(remote, "log", "--format=%s%n%b", "main")
        assert "two (remote only)" in log and "three (b only)" in log and "anthropic" not in log.lower()


if __name__ == "__main__":
    test_messages()
    test_rewrite()
    test_push_never_loses_remote_commits()
    test_clean_then_push_publishes()
    test_stale_clone_follows_cleaned_remote()
    test_work_on_both_sides_stops()
    print("deai: all checks passed")
