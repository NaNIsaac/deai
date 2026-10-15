# deai

[![PyPI](https://img.shields.io/pypi/v/git-deai)](https://pypi.org/project/git-deai/) [![Tests](https://github.com/NaNIsaac/deai/actions/workflows/tests.yml/badge.svg)](https://github.com/NaNIsaac/deai/actions/workflows/tests.yml) [![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**Remove AI co-author credits from your git history. Human co-authors and file contents stay as they are.**

[한국어](README.ko.md)

Before:

```
c72d54a docs: update README
        🤖 Generated with [Claude Code](https://claude.com/claude-code)
        Co-Authored-By: Claude <noreply@anthropic.com>
6b98cbb fix: handle empty input
        Co-authored-by: Jane Doe <jane@example.com>
049c5fb feat: add parser
        Co-Authored-By: Claude <noreply@anthropic.com>
```

After `deai clean`:

```
c70f42d docs: update README
24d6828 fix: handle empty input
        Co-authored-by: Jane Doe <jane@example.com>
0223c1d feat: add parser
```

Try it on your own repositories. `scan` only reads:

```console
$ uvx --from git-deai deai scan -r ~/code
AI credits  ~/code/my-app  (3 commits; trailers 2, AI author/committer 0)
            trailer: c72d54a 049c5fb
```

AI coding tools append `Co-Authored-By: Claude <noreply@anthropic.com>` and similar lines to commit
messages. GitHub reads them and lists the tool under your repository's **Contributors**. `deai` finds
these credits across your repositories, backs up, and rewrites the messages. Nothing is pushed unless
you ask.

## Install
Requires Python 3.10+ and git. There are no other dependencies.

```bash
pip install git-deai
# or, as an isolated tool
uv tool install git-deai     # recommended
pipx install git-deai
# or, from a local clone
uv tool install -e .
```

The package is `git-deai`; the command it installs is `deai`.
To try it without installing: `uvx --from git-deai deai --help`.

## Usage

**1. Scan (read-only).** Scanning only reports; it changes nothing.

```bash
deai scan                          # the repository in the current directory
deai scan path/to/repo             # one repository
deai scan -r ~/code                # every repository under a folder
```

```
AI credits  /home/me/code/my-app  (96 commits; trailers 51, AI author/committer 0)
            trailer: faea929 e37c10a 2ce9a9c 7a5f1ab ...
     clean  /home/me/code/notes   (8 commits; trailers 0, AI author/committer 0)
    shared  /home/me/code/xarray  (6578 commits; trailers 96, AI author/committer 1)
            by others: Deepak Cherian <...>, ...
```

| mark | meaning |
|---|---|
| `clean` | nothing to do |
| `AI credits` | your commits carry AI credits; `clean` will fix them |
| `shared` | someone else's commits carry AI credits (a fork or shared history); skipped by default |

**2. Clean (rewrites history).**

```bash
deai clean path/to/repo            # shows the scan, asks y/N, backs up, rewrites
deai clean -r ~/code               # every repository found (shared ones skipped)
deai clean -r ~/code --yes --push  # no question; force-push afterwards
```

**3. Publish.** Without `--push`, nothing leaves your machine. When you are happy with the result,
run the same command again with `--push`; `scan` marks such repositories `unpushed` until then.
Do not use `git push --all`: it would also push stale local branches over newer remote ones. Do not
`git pull` a cleaned branch either: it merges the old history, AI credits included, back in.

GitHub can take a while to refresh the Contributors list after the push.

## Options

| option | commands | what it does |
|---|---|---|
| `-r`, `--recursive` | scan, clean | find repositories below each path |
| `--me EMAIL` | scan, clean | another e-mail of yours (repeatable). `git config user.email` is always included. |
| `--yes` | clean | do not ask before rewriting |
| `--push` | clean | force-push branches (`--force-with-lease`) and tags afterwards |
| `--as 'Name <email>'` | clean | identity for commits authored by an AI (default: `git config user.*`) |
| `--include-shared` | clean | also rewrite `shared` repositories (rarely what you want) |

## What is removed
- `Co-authored-by:` trailers whose name or e-mail matches an AI tool. **Human co-authors stay.**
- "Generated with \<AI tool\>" lines, e.g. `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
- AI author and committer identities, which are re-attributed to you.

Matched tools: Claude/Anthropic, GitHub Copilot, Cursor, ChatGPT/OpenAI/Codex, Gemini, Devin, Aider,
Codeium/Windsurf, Tabnine, CodeWhisperer/Amazon Q, Jules, Sweep.

## Safety
- **A clean worktree is required.** `clean` refuses to run if tracked files have uncommitted changes.
- **A backup is made first.** Every branch and tag is saved to `.git/deai-backup-<time>.bundle`.
  To restore it:
  ```bash
  git fetch --force .git/deai-backup-20261014-222005.bundle 'refs/*:refs/*'
  ```
- **Pushes never lose remote commits.** `--push` fetches first.
  - A local branch that is behind its remote is fast-forwarded before the rewrite.
  - A branch that has diverged from its remote is compared commit by commit (`git cherry`, which
    matches a rewritten commit to its original). If the remote has nothing the branch lacks, the
    branch is pushed. If the branch has nothing the remote lacks (the remote was cleaned from
    another machine), the branch is moved to the remote's history. If both sides have new work,
    deai stops and tells you to `git rebase` onto the remote.
  - Each branch is force-pushed with an explicit lease on the commit seen at fetch time.
  - Only branches with an upstream are pushed; local-only branches stay local.
- **Forks are protected.** A repository whose flagged commits were written by other people is
  marked `shared` and skipped. Rewriting it would split your fork from upstream.

## Things to know
- **Commit hashes change** from the first cleaned commit onward. Anyone else with a clone must
  re-clone (or `git fetch && git reset --hard origin/<branch>`).
- **Open pull requests** from a rewritten branch need to be re-created.
- **GPG-signed commits** lose their signatures, because the signed content changed.
- **Protected branches** on GitHub may reject the force-push. Allow force-pushes temporarily, or push
  to a new branch.

## Stop it from coming back
Turn the attribution off in your AI tool. In Claude Code, add this to `~/.claude/settings.json`
(an empty string removes that line; the older `includeCoAuthoredBy` is deprecated):

```json
{ "attribution": { "commit": "", "pr": "" } }
```

## How it works
`git fast-export --branches --tags` → message filter (stdlib Python) → `git fast-import --force`.
There is no git-filter-repo dependency. File contents are passed through untouched, so every tree is
byte-identical to the original.

## Test
```bash
python tests/test_deai.py
```

## License

MIT, see [LICENSE](LICENSE).
