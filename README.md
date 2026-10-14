# deai

AI coding tools append `Co-Authored-By: Claude <noreply@anthropic.com>` (or Copilot, Cursor, ...)
to commit messages. GitHub reads the trailer and lists the tool as a contributor. `deai` finds those
credits across your repositories and rewrites the history without them.

```
uv tool install -e .                  # once; puts `deai` on PATH

deai scan -r D:/03_Develop            # report only; nothing changes
deai clean PATH                       # asks, backs up, rewrites
deai clean -r D:/03_Develop --yes --push
```

## What it removes
- `Co-authored-by:` trailers whose name or e-mail matches an AI tool. Human co-authors stay.
- "Generated with <AI tool>" lines, e.g. `🤖 Generated with [Claude Code](...)`.
- AI author/committer identities. These are re-attributed to `git config user.name/email`, or to
  `--as 'Name <email>'`.

Matched tools: Claude/Anthropic, Copilot, Cursor, ChatGPT/OpenAI/Codex, Gemini, Devin, Aider,
Codeium/Windsurf, Tabnine, CodeWhisperer/Amazon Q, Jules, Sweep.

## Safety
- **Report first.** `scan` never writes anything.
- **Clean worktree required.** `clean` refuses to run if tracked files have uncommitted changes.
- **Backup.** Every branch and tag is saved to `.git/deai-backup-<time>.bundle` first. To restore:
  `git fetch .git/deai-backup-....bundle 'refs/*:refs/*' --force`.
- **Local refs only.** Only local branches and tags are rewritten. Remote-tracking refs keep the old
  history, so `--push` uses `--force-with-lease` against what the remote really has.
- **Shared history.** A repository is marked `shared` and skipped when a flagged commit was written
  by someone else, as in a fork of an upstream project. Rewriting such a repository would split it
  from upstream. Add `--me EMAIL` for your other addresses. `--include-shared` overrides the skip.
- **Changed hashes.** Every commit hash from the first cleaned commit on changes. Other clones must
  re-clone or rebase. Open pull requests from rewritten branches must be re-created.

The rewrite pipes `git fast-export` → message filter → `git fast-import`. It is stdlib Python and
needs no git-filter-repo.

## Check
```
python tests/test_deai.py
```
