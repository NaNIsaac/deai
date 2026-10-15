# deai

**Remove AI co-author credits from your git history.**
**git 기록에서 AI 공동저자 표시를 지웁니다.**

[English](#english) · [한국어](#한국어)

---

## English

### Why
AI coding tools add a line like this to your commit messages:

```
Co-Authored-By: Claude <noreply@anthropic.com>
```

GitHub reads that line, so the tool then shows up in your repository's **Contributors** list. Copilot,
Cursor, Codex and others do the same. `deai` finds these credits in all your repositories and
rewrites the history without them. Your code does not change.

### Install
Requires Python 3.10+ and git. There are no other dependencies.

```bash
pip install deai
# or, as an isolated tool
uv tool install deai     # recommended
pipx install deai
# or, from a local clone
uv tool install -e .
```

### Usage

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
run the same command again with `--push`. Do not use `git push --all`: it would also push stale
local branches over newer remote ones.

GitHub can take a while to refresh the Contributors list after the push.

### Options

| option | commands | what it does |
|---|---|---|
| `-r`, `--recursive` | scan, clean | find repositories below each path |
| `--me EMAIL` | scan, clean | another e-mail of yours (repeatable). `git config user.email` is always included. |
| `--yes` | clean | do not ask before rewriting |
| `--push` | clean | force-push branches (`--force-with-lease`) and tags afterwards |
| `--as 'Name <email>'` | clean | identity for commits authored by an AI (default: `git config user.*`) |
| `--include-shared` | clean | also rewrite `shared` repositories (rarely what you want) |

### What is removed
- `Co-authored-by:` trailers whose name or e-mail matches an AI tool. **Human co-authors stay.**
- "Generated with \<AI tool\>" lines, e.g. `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
- AI author and committer identities, which are re-attributed to you.

Matched tools: Claude/Anthropic, GitHub Copilot, Cursor, ChatGPT/OpenAI/Codex, Gemini, Devin, Aider,
Codeium/Windsurf, Tabnine, CodeWhisperer/Amazon Q, Jules, Sweep.

### Safety
- **A clean worktree is required.** `clean` refuses to run if tracked files have uncommitted changes.
- **A backup is made first.** Every branch and tag is saved to `.git/deai-backup-<time>.bundle`.
  To restore it:
  ```bash
  git fetch --force .git/deai-backup-20261014-222005.bundle 'refs/*:refs/*'
  ```
- **Pushes never lose remote commits.** `--push` fetches first.
  - A local branch that is behind its remote is fast-forwarded before the rewrite.
  - A branch that has diverged from its remote stops the run.
  - Each branch is force-pushed with an explicit lease on the commit seen at fetch time.
  - Only branches with an upstream are pushed; local-only branches stay local.
- **Forks are protected.** A repository whose flagged commits were written by other people is
  marked `shared` and skipped. Rewriting it would split your fork from upstream.

### Things to know
- **Commit hashes change** from the first cleaned commit onward. Anyone else with a clone must
  re-clone (or `git fetch && git reset --hard origin/<branch>`).
- **Open pull requests** from a rewritten branch need to be re-created.
- **GPG-signed commits** lose their signatures, because the signed content changed.
- **Protected branches** on GitHub may reject the force-push. Allow force-pushes temporarily, or push
  to a new branch.

### Stop it from coming back
Turn the attribution off in your AI tool. In Claude Code, add this to `~/.claude/settings.json`
(an empty string removes that line; the older `includeCoAuthoredBy` is deprecated):

```json
{ "attribution": { "commit": "", "pr": "" } }
```

### How it works
`git fast-export --branches --tags` → message filter (stdlib Python) → `git fast-import --force`.
There is no git-filter-repo dependency. File contents are passed through untouched, so every tree is
byte-identical to the original.

### Test
```bash
python tests/test_deai.py
```

---

## 한국어

### 왜 필요한가요
AI 코딩 도구는 커밋 메시지 끝에 이런 줄을 붙입니다.

```
Co-Authored-By: Claude <noreply@anthropic.com>
```

GitHub는 이 줄을 읽어서 저장소의 **Contributors** 목록에 AI를 올립니다. Copilot, Cursor, Codex 등도
마찬가지입니다. `deai`는 내 저장소 전체에서 이런 표시를 찾아 git 기록에서 지웁니다. 코드는 그대로입니다.

### 설치
Python 3.10 이상과 git만 있으면 됩니다. 다른 의존성은 없습니다.

```bash
pip install deai
# 또는 격리된 도구로
uv tool install deai     # 추천
pipx install deai
# 또는 내려받은 폴더에서
uv tool install -e .
```

### 사용법

**1. 점검 (읽기만 함).** 결과만 보여주고 아무것도 바꾸지 않습니다.

```bash
deai scan                          # 현재 폴더의 저장소
deai scan 경로/저장소               # 저장소 하나
deai scan -r ~/code                # 폴더 아래 모든 저장소
```

| 표시 | 뜻 |
|---|---|
| `clean` | 고칠 것 없음 |
| `AI credits` | 내 커밋에 AI 표시가 있음. `clean`으로 지울 수 있음 |
| `shared` | **다른 사람** 커밋에 AI 표시가 있음 (fork 등). 기본적으로 건너뜀 |

**2. 정리 (기록을 다시 씀).**

```bash
deai clean 경로/저장소              # 점검 결과 → y/N 확인 → 백업 → 다시 쓰기
deai clean -r ~/code               # 찾은 저장소 전부 (shared는 제외)
deai clean -r ~/code --yes --push  # 확인 없이, 끝나면 force-push까지
```

**3. GitHub에 반영.** `--push`를 붙이지 않으면 내 컴퓨터 밖으로 아무것도 나가지 않습니다. 결과를 확인한 뒤
같은 명령에 `--push`를 붙여 다시 실행하세요. `git push --all`은 쓰지 마세요. 원격보다 뒤처진 로컬 브랜치까지
덮어써서 원격의 최신 커밋이 사라질 수 있습니다.

push한 뒤 GitHub의 Contributors 목록이 갱신되기까지 시간이 좀 걸릴 수 있습니다.

### 옵션

| 옵션 | 명령 | 하는 일 |
|---|---|---|
| `-r`, `--recursive` | scan, clean | 경로 아래 저장소를 모두 찾음 |
| `--me EMAIL` | scan, clean | 내 다른 이메일 (여러 번 지정 가능). `git config user.email`은 항상 포함 |
| `--yes` | clean | 확인 질문 없이 진행 |
| `--push` | clean | 끝나면 브랜치(`--force-with-lease`)와 태그를 force-push |
| `--as '이름 <이메일>'` | clean | AI가 작성자로 된 커밋을 바꿀 이름 (기본값: `git config user.*`) |
| `--include-shared` | clean | `shared` 저장소도 다시 씀 (보통은 쓰지 마세요) |

### 지우는 것
- AI 도구 이름이나 이메일이 들어간 `Co-authored-by:` 줄. **사람 공동저자 줄은 남깁니다.**
- `🤖 Generated with [Claude Code](...)` 같은 "Generated with \<AI 도구\>" 줄
- AI가 작성자나 커미터로 된 커밋. 이 커밋들은 내 이름으로 바꿉니다.

### 안전장치
- **커밋 안 한 변경이 있으면 실행하지 않습니다.**
- **먼저 백업합니다.** 모든 브랜치와 태그를 `.git/deai-backup-<시각>.bundle`로 저장합니다. 되돌리려면:
  ```bash
  git fetch --force .git/deai-backup-20261014-222005.bundle 'refs/*:refs/*'
  ```
- **원격 커밋을 잃지 않습니다.** `--push`를 붙이면 먼저 fetch합니다.
  - 원격보다 뒤처진 로컬 브랜치는 먼저 fast-forward합니다.
  - 원격과 갈라진 브랜치가 있으면 멈춥니다.
  - 브랜치마다 fetch 시점의 커밋을 lease로 걸어 force-push합니다.
  - upstream이 있는 브랜치만 push하고, 로컬 전용 브랜치는 그대로 둡니다.
- **fork는 보호합니다.** 다른 사람이 쓴 커밋이 걸린 저장소는 `shared`로 표시하고 건너뜁니다.
  다시 쓰면 upstream과 기록이 갈라지기 때문입니다.

### 알아둘 점
- **커밋 해시가 바뀝니다.** 처음 고쳐진 커밋부터 그 뒤가 모두 바뀝니다. 다른 사람이 clone해 둔 저장소는
  다시 clone하거나 `git fetch && git reset --hard origin/<브랜치>`를 해야 합니다.
- **열린 PR**이 다시 쓴 브랜치에 있으면 PR을 새로 만들어야 합니다.
- **GPG 서명**은 사라집니다. 서명한 내용이 바뀌었기 때문입니다.
- **보호된 브랜치**는 force-push가 거절될 수 있습니다. 잠깐 허용하거나 새 브랜치로 push하세요.

### 다시 생기지 않게 하기
AI 도구에서 공동저자 표시를 끄세요. Claude Code라면 `~/.claude/settings.json`에 다음을 넣습니다
(빈 문자열이면 그 줄을 넣지 않습니다. 예전 설정 `includeCoAuthoredBy`는 deprecated입니다).

```json
{ "attribution": { "commit": "", "pr": "" } }
```

### 동작 방식
`git fast-export --branches --tags` → 메시지 필터(표준 라이브러리 Python) → `git fast-import --force`.
git-filter-repo가 필요 없습니다. 파일 내용은 손대지 않으므로 모든 트리가 원래와 바이트 단위로 같습니다.

---

MIT License
