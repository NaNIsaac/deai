"""deai: find and remove AI co-author credits from git history.

AI coding tools append trailers such as ``Co-Authored-By: Claude <noreply@anthropic.com>``
to commit messages. GitHub reads those trailers and lists the tool as a contributor.
deai finds them, and on request rewrites the history without them.

    deai scan [PATH ...] [-r]       report, change nothing
    deai clean [PATH ...] [-r] [--yes] [--push]

What ``clean`` removes from every commit message:
- ``Co-authored-by:`` trailers whose name or e-mail matches a known AI tool;
- "Generated with <AI tool>" lines (e.g. "🤖 Generated with [Claude Code](...)").
Human co-authors stay. Commits *authored* or *committed* by an AI identity are re-attributed
to the repository's ``git config user.name / user.email`` (or ``--as``).

Safety:
- the worktree must have no uncommitted changes to tracked files;
- a full backup bundle is written to ``.git/deai-backup-<time>.bundle`` first;
- only local branches and tags are rewritten. Remote-tracking refs keep the old history,
  so ``--push`` can use ``--force-with-lease`` against what the remote really has;
- nothing is pushed unless ``--push`` is given.

Rewriting changes every commit hash from the first cleaned commit on. Anyone else with a
clone must re-clone or rebase afterwards.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

AI = re.compile(
    r"claude|anthropic|copilot|cursor(agent)?\b|chatgpt|openai|\bcodex\b|gemini|\bdevin\b|"
    r"\baider\b|codeium|windsurf|tabnine|codewhisperer|amazon q\b|\bjules\b|sweep-?ai",
    re.IGNORECASE,
)
COAUTHOR = re.compile(r"^[ \t]*co-authored-by:[ \t]*(?P<who>.*)$", re.IGNORECASE)
GENERATED = re.compile(r"^.*\bgenerated (with|by)\b(?P<who>.*)$", re.IGNORECASE)
IDENT = re.compile(rb"^(?P<kind>author|committer) (?P<name>.*?) <(?P<email>[^>]*)> (?P<when>.*)$")
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".tox", "dist", "build"}


def is_ai(text: str) -> bool:
    return bool(AI.search(text))


def clean_message(msg: str) -> str:
    """Drop AI co-author trailers and "generated with <AI>" lines; keep everything else."""
    kept = []
    for line in msg.splitlines():
        m = COAUTHOR.match(line) or GENERATED.match(line)
        if m and is_ai(m["who"]):
            continue
        kept.append(line)
    while kept and not kept[-1].strip():          # the trailer block often leaves a blank tail
        kept.pop()
    return "\n".join(kept) + ("\n" if msg.endswith("\n") or kept else "")


# ───────────── git plumbing ─────────────

def git(repo: Path, *args: str, check: bool = True) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed in {repo}:\n{r.stderr.strip()}")
    return r.stdout


def find_repos(paths: list[str], recursive: bool) -> list[Path]:
    out = []
    for p in map(Path, paths or ["."]):
        p = p.resolve()
        if (p / ".git").exists():
            out.append(p)
            continue
        if not recursive:
            print(f"skip {p}: not a git repository (use -r to search below it)", file=sys.stderr)
            continue
        for root, dirs, _ in os.walk(p):
            if ".git" in dirs or (Path(root) / ".git").is_file():
                out.append(Path(root))
                dirs[:] = []                       # do not descend into a repository
                continue
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
    return sorted(set(out))


@dataclass
class Report:
    repo: Path
    commits: int = 0
    trailers: list[str] = field(default_factory=list)   # short hashes with an AI trailer/line
    idents: list[str] = field(default_factory=list)     # short hashes with an AI author/committer
    others: set[str] = field(default_factory=set)       # human authors of flagged commits who are not you

    @property
    def dirty(self) -> bool:
        return bool(self.trailers or self.idents)


def my_emails(repo: Path, extra: list[str]) -> set[str]:
    me = git(repo, "config", "user.email", check=False).strip()
    return {e.lower() for e in [me, *extra] if e}


def scan(repo: Path, me: list[str] | None = None) -> Report:
    """Flag commits with AI credits. A flagged commit by another human means shared history
    (a fork, a vendored project): rewriting it would split you from upstream."""
    r = Report(repo)
    if not git(repo, "rev-parse", "--verify", "-q", "HEAD", check=False).strip():
        return r                                   # empty repository
    mine = my_emails(repo, me or [])
    log = git(repo, "log", "--branches", "--tags", "--format=%h%x00%an <%ae>%x00%ae%x00%cn <%ce>%x00%B%x1e")
    for rec in filter(str.strip, log.split("\x1e")):
        h, author, email, committer, body = rec.strip("\n").split("\x00", 4)
        r.commits += 1
        flagged = False
        if clean_message(body) != clean_message_noop(body):
            r.trailers.append(h)
            flagged = True
        if is_ai(author) or is_ai(committer):
            r.idents.append(h)
            flagged = True
        if flagged and not is_ai(author) and email.lower() not in mine:
            r.others.add(author)
    return r


def clean_message_noop(msg: str) -> str:
    """The same normalisation as clean_message without removing anything (fair comparison)."""
    kept = msg.splitlines()
    while kept and not kept[-1].strip():
        kept.pop()
    return "\n".join(kept) + ("\n" if msg.endswith("\n") or kept else "")


# ───────────── rewrite ─────────────

def rewrite_stream(src, dst, ident: bytes) -> int:
    """Copy a ``git fast-export`` stream, cleaning commit messages and AI identities.

    Returns the number of commits changed. Blob and tag payloads pass through untouched;
    only the first ``data`` block after a ``commit`` command is a commit message.
    """
    changed, in_commit, msg_next, touched = 0, False, False, False
    while line := src.readline():
        if line.startswith(b"commit "):
            in_commit, msg_next, touched = True, True, False
        elif line.startswith((b"blob", b"tag ", b"reset ")):
            in_commit, msg_next = False, False
        elif in_commit and (m := IDENT.match(line.rstrip(b"\n"))):
            who = (m["name"] + b" <" + m["email"] + b">").decode("utf-8", "surrogateescape")
            if is_ai(who):
                line = m["kind"] + b" " + ident + b" " + m["when"] + b"\n"
                touched = True
        elif line.startswith(b"data "):
            payload = src.read(int(line[5:]))
            if msg_next:
                msg_next = False
                text = payload.decode("utf-8", "surrogateescape")
                new = clean_message(text)
                if new != clean_message_noop(text):
                    payload, touched = new.encode("utf-8", "surrogateescape"), True
                changed += touched
            dst.write(b"data %d\n" % len(payload) + payload)
            continue
        dst.write(line)
    return changed


@dataclass
class Tracked:
    branch: str        # local branch name
    remote: str        # e.g. origin
    remote_ref: str    # e.g. refs/heads/main on the remote
    upstream: str      # e.g. refs/remotes/origin/main
    oid: str = ""      # upstream commit at fetch time: the lease for the force-push


def tracked_branches(repo: Path) -> list[Tracked]:
    fmt = "%(refname:short)%00%(upstream:remotename)%00%(upstream:remoteref)%00%(upstream)"
    out = []
    for line in git(repo, "for-each-ref", f"--format={fmt}", "refs/heads").splitlines():
        b, remote, rref, up = line.split("\x00")
        oid = git(repo, "rev-parse", "-q", "--verify", up, check=False).strip() if up else ""
        if remote and oid:                         # upstream configured and present after fetch
            out.append(Tracked(b, remote, rref, up, oid))
    return out


def is_ancestor(repo: Path, a: str, b: str) -> bool:
    return subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", a, b],
                          check=False).returncode == 0


def unique(repo: Path, base: str, head: str) -> int:
    """Commits in ``head`` whose change is not in ``base`` under any hash (``git cherry``).

    deai only edits messages, so a rewritten commit matches its original here.
    """
    return sum(line.startswith("+") for line in git(repo, "cherry", base, head).splitlines())


def flagged(repo: Path, rev_range: str) -> int:
    """Commits in ``rev_range`` that carry AI credits."""
    log = git(repo, "log", rev_range, "--format=%an <%ae>%x00%cn <%ce>%x00%B%x1e")
    n = 0
    for rec in filter(str.strip, log.split("\x1e")):
        author, committer, body = rec.strip("\n").split("\x00", 2)
        n += clean_message(body) != clean_message_noop(body) or is_ai(author) or is_ai(committer)
    return n


def unpushed(repo: Path) -> list[str]:
    """Branches whose remote still has AI credits that the local history already dropped,
    i.e. ``clean`` ran without ``--push``. Uses remote-tracking refs as they are; no fetch."""
    return [t.branch for t in tracked_branches(repo)
            if not is_ancestor(repo, t.upstream, t.branch) and not unique(repo, t.branch, t.upstream)
            and flagged(repo, f"{t.branch}..{t.upstream}") and not flagged(repo, f"{t.upstream}..{t.branch}")]


def backup(repo: Path) -> Path:
    path = repo / ".git" / f"deai-backup-{time.strftime('%Y%m%d-%H%M%S')}.bundle"
    if not path.exists():
        git(repo, "bundle", "create", str(path), "--branches", "--tags")
    return path


def sync_with_remote(repo: Path) -> list[Tracked]:
    """Fetch and line every tracked branch up with its upstream so a force-push loses nothing.

    - behind: fast-forward.
    - diverged, but every remote commit has an equivalent here (e.g. this side was rewritten,
      or was rewritten and then got new commits): keep the local branch; the push loses nothing.
    - diverged, but every local commit has an equivalent on the remote (the remote was
      rewritten elsewhere, this clone is stale): move the branch to the remote's history.
    - both sides have work the other lacks: stop. Merging would bring the old history back.
    """
    git(repo, "fetch", "--all", "--quiet")
    current = git(repo, "branch", "--show-current").strip()
    tracked = tracked_branches(repo)
    for t in tracked:
        up = t.upstream.removeprefix("refs/remotes/")
        if is_ancestor(repo, t.upstream, t.branch):
            continue                               # local contains the remote: fine
        if is_ancestor(repo, t.branch, t.upstream):
            why = "it was behind the remote"
        elif not unique(repo, t.branch, t.upstream):
            continue                               # nothing on the remote that is not here
        elif not unique(repo, t.upstream, t.branch):
            why = "the remote has the same commits under rewritten hashes; this clone was stale"
        else:
            mine, theirs = unique(repo, t.upstream, t.branch), unique(repo, t.branch, t.upstream)
            raise RuntimeError(
                f"branch {t.branch} has diverged from {up}: {mine} commit(s) only here, "
                f"{theirs} only on the remote. Put yours on top of the remote with "
                f"`git rebase {up}` (commits the remote already has in rewritten form are "
                f"dropped), then run deai again. Do not `git pull` or merge: that brings the old "
                f"history back.")
        print(f"  backup: {backup(repo)}")
        if t.branch == current:
            git(repo, "reset", "-q", "--keep", t.upstream)
        else:
            git(repo, "branch", "-q", "-f", t.branch, t.upstream)
        print(f"  moved {t.branch} to {up} ({why})")
    return tracked


def push_rewritten(repo: Path, tracked: list[Tracked]) -> None:
    """Force-push each tracked branch with an explicit lease on the commit seen at fetch time."""
    if not tracked:
        print("  no branch has an upstream; nothing to push")
        return
    for t in tracked:
        git(repo, "push", "--quiet", f"--force-with-lease={t.remote_ref}:{t.oid}", t.remote,
            f"refs/heads/{t.branch}:{t.remote_ref}")
        print(f"  pushed {t.branch} -> {t.remote}/{t.remote_ref.removeprefix('refs/heads/')}")
    for remote in sorted({t.remote for t in tracked}):
        git(repo, "push", "--quiet", "--force", "--tags", remote)
        print(f"  pushed tags -> {remote}")


def clean(repo: Path, as_ident: str | None, push: bool) -> int:
    if git(repo, "status", "--porcelain", "--untracked-files=no").strip():
        raise RuntimeError("uncommitted changes to tracked files; commit or stash them first")
    if as_ident is None:
        name, email = git(repo, "config", "user.name").strip(), git(repo, "config", "user.email").strip()
        as_ident = f"{name} <{email}>"
    if not re.fullmatch(r"[^<>]+ <[^<>]+>", as_ident) or is_ai(as_ident):
        raise RuntimeError(f"--as must be a human 'Name <email>', got {as_ident!r}")
    tracked = sync_with_remote(repo) if push else []
    if not scan(repo).dirty:                      # the stale side was dropped in favour of a clean remote
        print("  already clean after syncing with the remote")
        return 0

    bundle = backup(repo)

    exp = subprocess.Popen(["git", "-C", str(repo), "fast-export", "--branches", "--tags",
                            "--signed-tags=strip", "--use-done-feature"], stdout=subprocess.PIPE)
    imp = subprocess.Popen(["git", "-C", str(repo), "fast-import", "--force", "--quiet"],
                           stdin=subprocess.PIPE)
    assert exp.stdout and imp.stdin
    changed = rewrite_stream(exp.stdout, imp.stdin, as_ident.encode("utf-8"))
    imp.stdin.close()
    if exp.wait() or imp.wait():
        raise RuntimeError(f"fast-export/fast-import failed; history is unchanged or restorable from {bundle}")
    git(repo, "reset", "-q", "--keep", "HEAD")    # trees are identical; refresh the index only
    print(f"  rewrote {changed} commit(s); backup: {bundle}")

    if push:
        push_rewritten(repo, tracked)
    else:
        print("  not pushed. Run again with --push to publish (it fetches first and never pushes a stale branch).")
    return changed


def publish(repo: Path) -> None:
    """Push a history that ``clean`` already rewrote locally."""
    if git(repo, "status", "--porcelain", "--untracked-files=no").strip():
        raise RuntimeError("uncommitted changes to tracked files; commit or stash them first")
    push_rewritten(repo, sync_with_remote(repo))


# ───────────── CLI ─────────────

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="deai", description=(__doc__ or "").split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, help_ in (("scan", "report AI credits, change nothing"),
                        ("clean", "rewrite history without AI credits")):
        p = sub.add_parser(name, help=help_)
        p.add_argument("paths", nargs="*", help="repositories (default: current directory)")
        p.add_argument("-r", "--recursive", action="store_true", help="find repositories below PATH")
        p.add_argument("--me", action="append", default=[], metavar="EMAIL",
                       help="another e-mail of yours (repeatable; git config user.email is always included)")
    c = sub.choices["clean"]
    c.add_argument("--yes", action="store_true", help="do not ask before rewriting")
    c.add_argument("--push", action="store_true", help="force-push branches and tags afterwards")
    c.add_argument("--as", dest="as_ident", metavar="'NAME <EMAIL>'",
                   help="identity for AI-authored commits (default: git config user.*)")
    c.add_argument("--include-shared", action="store_true",
                   help="also rewrite repositories where other people's commits carry AI credits")
    a = ap.parse_args(argv)

    repos = find_repos(a.paths, a.recursive)
    if not repos:
        print("no repositories found", file=sys.stderr)
        return 1
    reports = [scan(r, a.me) for r in repos]
    pending = {rp.repo: unpushed(rp.repo) for rp in reports if not rp.dirty}
    for rp in reports:
        mark = ("shared" if rp.others else "AI credits" if rp.dirty
                else "unpushed" if pending[rp.repo] else "clean")
        print(f"{mark:>10}  {rp.repo}  ({rp.commits} commits; trailers {len(rp.trailers)}, "
              f"AI author/committer {len(rp.idents)})")
        for kind, hs in (("trailer", rp.trailers), ("identity", rp.idents)):
            if hs:
                print(f"            {kind}: {' '.join(hs[:8])}{' ...' if len(hs) > 8 else ''}")
        if rp.others:
            names = sorted(rp.others)
            print(f"            by others: {', '.join(names[:4])}{' ...' if len(names) > 4 else ''}")
        if pending.get(rp.repo):
            print(f"            cleaned here, not pushed: {', '.join(pending[rp.repo])}")
    if a.cmd == "scan":
        if any(rp.others for rp in reports):
            print("\n'shared': other people's commits are flagged (fork or shared history). "
                  "clean skips these unless --include-shared; add --me for your other e-mails.")
        if any(pending.values()):
            print("\n'unpushed': the remote still has the AI credits. Publish with `deai clean --push`; "
                  "do not `git pull`, which merges the old history back in.")
        return 0

    todo = [rp for rp in reports if rp.dirty and (a.include_shared or not rp.others)]
    to_publish = [r for r, branches in pending.items() if branches] if a.push else []
    for rp in reports:
        if rp.dirty and rp.others and not a.include_shared:
            print(f"skip {rp.repo}: shared history (see --include-shared)")
    if not todo and not to_publish:
        print("nothing to clean" + ("" if a.push or not any(pending.values()) else
                                    "; cleaned history is waiting to be pushed (add --push)"))
        return 0
    if not a.yes:
        n = len(todo) + len(to_publish)
        what = "Rewrite and push" if a.push else "Rewrite"
        ans = input(f"{what} history of {n} repositor{'y' if n == 1 else 'ies'}? "
                    "Commit hashes will change. [y/N] ")
        if ans.strip().lower() not in ("y", "yes"):
            print("aborted")
            return 1
    failed = 0
    for repo, action in [*((rp.repo, "cleaning") for rp in todo), *((r, "pushing") for r in to_publish)]:
        print(f"{action} {repo}")
        try:
            clean(repo, a.as_ident, a.push) if action == "cleaning" else publish(repo)
        except RuntimeError as e:
            failed += 1
            print(f"  error: {e}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
