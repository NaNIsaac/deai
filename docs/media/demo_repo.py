"""Create the throwaway repository that docs/media/demo.tape runs deai on.

uv run python docs/media/demo_repo.py DIR

The three commits match the README's "Before" example. Names, e-mails and dates are fixed so the
commit hashes are the same on every run. The global git config is left out, as in
tests/test_deai.py, because a global commit-msg hook may strip the very trailers this commits.
"""

import os
import subprocess
import sys
from pathlib import Path

ME = ("Demo User", "demo@example.com")
COMMITS = [
    ("parser.py", "feat: add parser\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n"),
    ("parser.py", "fix: handle empty input\n\nCo-authored-by: Jane Doe <jane@example.com>\n"),
    (
        "README.md",
        (
            "docs: update README\n\n"
            "Generated with [Claude Code](https://claude.com/claude-code)\n\n"
            "Co-Authored-By: Claude <noreply@anthropic.com>\n"
        ),
    ),
]


def git(repo: Path, *args: str, env: dict | None = None) -> None:
    env = (env or os.environ) | {"GIT_CONFIG_GLOBAL": os.devnull}
    subprocess.run(["git", "-C", str(repo), *args], check=True, env=env, capture_output=True)


def main(repo: Path) -> None:
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.name", ME[0])
    git(repo, "config", "user.email", ME[1])
    git(repo, "config", "core.autocrlf", "false")
    for k, (name, message) in enumerate(COMMITS):
        path = repo / name
        with path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(f"line {k}\n")
        git(repo, "add", name)
        date = f"2026-10-0{k + 1}T12:00:00+09:00"
        env = os.environ | {"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
        git(repo, "commit", "-q", "-m", message, env=env)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
