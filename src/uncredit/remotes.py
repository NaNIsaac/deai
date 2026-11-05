"""Read remote history in disposable bare partial clones; cleaning remains local."""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit


class RemoteError(RuntimeError):
    pass


def remote_url(value: str) -> str | None:
    if re.match(r"^(?:https?|ssh|git|file)://|^[^/\s@:]+@[^:\s]+:", value):
        return value
    if Path(value).exists():
        return None
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+", value):
        return f"https://github.com/{value.removesuffix('.git')}.git"
    return None


@contextmanager
def clone(url: str):
    with tempfile.TemporaryDirectory(prefix="uncredit-scan-") as folder:
        repo = Path(folder) / "repo.git"
        try:
            process = subprocess.Popen(
                ["git", "clone", "--filter=blob:none", "--bare", "--quiet", "--", url, str(repo)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                env=os.environ | {"GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"},
            )
        except OSError as exc:
            raise RemoteError(f"cannot start git: {exc}") from exc
        try:
            _, error = process.communicate()
        except BaseException:
            process.kill()
            process.communicate()
            raise
        if process.returncode:
            detail = error.decode("utf-8", errors="replace").strip()
            raise RemoteError(
                f"clone failed; check the URL and git authentication "
                f"(credential helper or gh auth setup-git): {detail}"
            )
        yield repo


def github_repos(owner: str, include_forks: bool, include_archived: bool) -> list[str]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", owner):
        raise RemoteError("expected a GitHub user or organization name")
    try:
        result = subprocess.run(
            [
                "gh",
                "repo",
                "list",
                owner,
                "--limit",
                "100000",
                "--json",
                "nameWithOwner,url,isArchived,isFork",
            ],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=os.environ | {"GH_PROMPT_DISABLED": "1"},
            check=False,
        )
    except OSError as exc:
        raise RemoteError(f"cannot list repositories with gh: {exc}") from exc
    if result.returncode:
        raise RemoteError(f"GitHub listing failed; check gh auth status: {result.stderr.strip()}")
    try:
        repos = json.loads(result.stdout)
    except ValueError as exc:
        raise RemoteError("gh returned invalid repository JSON") from exc
    if not isinstance(repos, list):
        raise RemoteError("gh repository list must be an array")
    urls = []
    for repo in repos:
        if (
            not isinstance(repo, dict)
            or not isinstance(repo.get("url"), str)
            or type(repo.get("isFork")) is not bool
            or type(repo.get("isArchived")) is not bool
            or remote_url(repo["url"]) != repo["url"]
        ):
            raise RemoteError("gh returned an invalid repository record")
        if (repo["isFork"] and not include_forks) or (repo["isArchived"] and not include_archived):
            continue
        urls.append(repo["url"])
    return list(dict.fromkeys(urls))


def instructions(url: str, options: list[str]) -> None:
    name = urlsplit(url).path.rsplit("/", 1)[-1].removesuffix(".git")
    name = re.sub(r"[^A-Za-z0-9_.-]", "-", name)
    if name in {"", ".", ".."}:
        name = "repository"

    def command(args):
        if os.name == "nt":
            return "& " + " ".join("'" + arg.replace("'", "''") + "'" for arg in args)
        return shlex.join(args)

    print("Remote clean is a plan only. Run these locally; the last step publishes with leases:")
    for args in (
        ["git", "clone", "--", url, name],
        ["uncredit", "clean", name, *options],
        ["uncredit", "clean", name, *options, "--push"],
    ):
        print(command(args))
