# deai

[![PyPI](https://img.shields.io/pypi/v/git-deai)](https://pypi.org/project/git-deai/) [![Tests](https://github.com/NaNIsaac/deai/actions/workflows/ci.yml/badge.svg)](https://github.com/NaNIsaac/deai/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**git 기록에서 AI 공동저자 표시를 지웁니다. 사람 공동저자와 파일 내용은 그대로 둡니다.**

[English](README.md)

AI 코딩 도구는 커밋 메시지 끝에 `Co-Authored-By: Claude <noreply@anthropic.com>` 같은 줄을 붙입니다.
GitHub는 이 줄을 읽어서 저장소의 **Contributors** 목록에 그 도구를 올립니다. `deai`는 내 저장소 전체에서
이런 표시를 찾아 백업한 뒤 커밋 메시지를 다시 씁니다. 요청하지 않으면 아무것도 push하지 않습니다.

전:

```
c72d54a docs: update README
        🤖 Generated with [Claude Code](https://claude.com/claude-code)
        Co-Authored-By: Claude <noreply@anthropic.com>
6b98cbb fix: handle empty input
        Co-authored-by: Jane Doe <jane@example.com>
049c5fb feat: add parser
        Co-Authored-By: Claude <noreply@anthropic.com>
```

`deai clean` 후:

```
c70f42d docs: update README
24d6828 fix: handle empty input
        Co-authored-by: Jane Doe <jane@example.com>
0223c1d feat: add parser
```

내 저장소에서 바로 확인해 보세요. `scan`은 읽기만 합니다.

```console
$ uvx --from git-deai deai scan -r ~/code
AI credits  ~/code/my-app  (3 commits; trailers 2, AI author/committer 0)
            trailer: c72d54a 049c5fb
```

## 설치
Python 3.10 이상과 git이 필요합니다.
Termux는 CI에서 테스트합니다.

```bash
pip install git-deai
# 또는 격리된 도구로
uv tool install git-deai     # 추천
pipx install git-deai
# 또는 내려받은 폴더에서
uv tool install -e .
```

패키지 이름은 `git-deai`이고, 설치되는 명령어는 `deai`입니다.
설치 없이 써 보려면: `uvx --from git-deai deai --help`

## 사용법

**1. 점검 (읽기만 함).** 결과만 보여주고 아무것도 바꾸지 않습니다.

```bash
deai scan                          # 현재 폴더의 저장소
deai scan 경로/저장소               # 저장소 하나
deai scan -r ~/code                # 폴더 아래 모든 저장소
```

```
AI credits  /home/me/code/my-app  (96 commits; trailers 51, AI author/committer 0)
            trailer: faea929 e37c10a 2ce9a9c 7a5f1ab ...
     clean  /home/me/code/notes   (8 commits; trailers 0, AI author/committer 0)
    shared  /home/me/code/xarray  (6578 commits; trailers 96, AI author/committer 1)
            by others: Deepak Cherian <...>, ...
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
같은 명령에 `--push`를 붙여 다시 실행하세요. 그 전까지 `scan`은 이런 저장소를 `unpushed`로 표시합니다.
`git push --all`은 쓰지 마세요. 원격보다 뒤처진 로컬 브랜치까지 덮어써서 원격의 최신 커밋이 사라질 수 있습니다.
정리한 브랜치에서 `git pull`도 하지 마세요. 옛 기록이 AI 표시와 함께 다시 merge됩니다.

push한 뒤 GitHub의 Contributors 목록이 갱신되기까지 시간이 좀 걸릴 수 있습니다.

## 옵션

| 옵션 | 명령 | 하는 일 |
|---|---|---|
| `-r`, `--recursive` | scan, clean | 경로 아래 저장소를 모두 찾음 |
| `--me EMAIL` | scan, clean | 내 다른 이메일 (여러 번 지정 가능). `git config user.email`은 항상 포함 |
| `--yes` | clean | 확인 질문 없이 진행 |
| `--push` | clean | 끝나면 브랜치와 다시 쓴 태그를 force-push (`--force-with-lease`) |
| `--as '이름 <이메일>'` | clean | AI가 작성자로 된 커밋을 바꿀 이름 (기본값: `git config user.*`) |
| `--include-shared` | clean | `shared` 저장소도 다시 씀 (보통은 쓰지 마세요) |

## 지우는 것
- AI 도구 이름이나 이메일이 들어간 `Co-authored-by:` 줄. **사람 공동저자 줄은 남깁니다.**
- `🤖 Generated with [Claude Code](...)` 같은 "Generated with \<AI 도구\>" 줄
- AI가 작성자나 커미터로 된 커밋. 이 커밋들은 내 이름으로 바꿉니다.

대상 도구: Claude/Anthropic, GitHub Copilot, Cursor, ChatGPT/OpenAI/Codex, Gemini, Devin, Aider,
Codeium/Windsurf, Tabnine, CodeWhisperer/Amazon Q, Jules, Sweep.

## 안전장치
- **커밋 안 한 변경이 있으면 실행하지 않습니다.**
- **먼저 백업합니다.** 모든 브랜치와 태그를 `.git/deai-backup-<시각>.bundle`로 저장합니다. 되돌리려면:
  ```bash
  git fetch --force .git/deai-backup-20261014-222005.bundle 'refs/*:refs/*'
  ```
- **원격 커밋을 잃지 않습니다.** `--push`를 붙이면 먼저 fetch합니다.
  - 원격보다 뒤처진 로컬 브랜치는 먼저 fast-forward합니다.
  - 원격과 갈라진 브랜치는 커밋 단위로 비교합니다(`git cherry`, 다시 쓴 커밋을 원래 커밋과 같은 것으로 봅니다).
    원격에만 있는 작업이 없으면 그대로 push합니다. 로컬에만 있는 작업이 없으면(다른 컴퓨터에서 이미 정리해 push한 경우)
    로컬 브랜치를 원격 기록으로 옮깁니다. 양쪽에 새 작업이 있으면 멈추고 `git rebase`로 원격 위에 올리라고 안내합니다.
  - 브랜치마다 fetch 시점의 커밋을 lease로 걸어 force-push합니다.
  - upstream이 있는 브랜치만 push하고, 로컬 전용 브랜치는 그대로 둡니다.
  - 원격 태그 중 이번에 다시 쓴 것만 fetch 시점의 태그를 lease로 걸어 push합니다. 다른 원격 태그와 로컬 전용 태그는 그대로 둡니다.
- **fork는 보호합니다.** 다른 사람이 쓴 커밋이 걸린 저장소는 `shared`로 표시하고 건너뜁니다.
  다시 쓰면 upstream과 기록이 갈라지기 때문입니다.

## 알아둘 점
- **커밋 해시가 바뀝니다.** 처음 고쳐진 커밋부터 그 뒤가 모두 바뀝니다. 다른 사람이 clone해 둔 저장소는
  다시 clone하거나 `git fetch && git reset --hard origin/<브랜치>`를 해야 합니다.
- **열린 PR**이 다시 쓴 브랜치에 있으면 PR을 새로 만들어야 합니다.
- **GPG 서명**은 사라집니다. 서명한 내용이 바뀌었기 때문입니다. 다시 쓴 기록을 가리키는 서명된 annotated 태그도 마찬가지입니다.
- **보호된 브랜치**는 force-push가 거절될 수 있습니다. 잠깐 허용하거나 새 브랜치로 push하세요.

## 다시 생기지 않게 하기
AI 도구에서 공동저자 표시를 끄세요. Claude Code라면 `~/.claude/settings.json`에 다음을 넣습니다
(빈 문자열이면 그 줄을 넣지 않습니다).

```json
{ "attribution": { "commit": "", "pr": "" } }
```

## 동작 방식
`git fast-export --branches --tags` → 메시지 필터(표준 라이브러리 Python) → `git fast-import --force`.
파일 내용은 손대지 않으므로 모든 트리가 원래와 바이트 단위로 같습니다.

## 테스트
```bash
python tests/test_deai.py
```

## 라이선스

MIT, [LICENSE](LICENSE) 참고.
