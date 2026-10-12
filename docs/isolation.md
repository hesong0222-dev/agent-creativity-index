# 격리 검증 기록 (2026-10-12)

기준 에이전트(A)와 스킬 에이전트(B)가 사용자 전역 설정(플러그인, `~/.claude/CLAUDE.md`, 훅, `~/.claude/skills`·`agents`·`commands`의 개인 항목)을 불러오지 않는지 `aci doctor`로 확인했다.

## 채택: 후보 1 (구독 로그인 그대로, 전역 설정 소스 배제)

```
claude -p --setting-sources project --strict-mcp-config --dangerously-skip-permissions < {prompt_file}
```

- `claude-base`: PASS. 보이는 것은 Claude Code 내장 스킬·내장 서브에이전트뿐. 플러그인·MCP·훅·CLAUDE.md 없음, 개인 스킬 30여 개 없음.
- `claude-skill`(위 명령 + `--plugin-dir {repo_root}`): PASS. 이 저장소 플러그인은 아직 스킬이 없어 목록에 보이지 않는다.
- 후보 2(`CLAUDE_CONFIG_DIR` 별도 폴더), 후보 3(`--bare`, API 키 전용)은 시도할 필요가 없었다.

### claude-base 점검 결과 원문

```
SKILLS:
skill: dataviz
skill: artifact-design
skill: artifact-diagramming
skill: artifact-capabilities
skill: update-config
skill: keybindings-help
skill: code-review
skill: simplify
skill: fewer-permission-prompts
skill: loop
skill: schedule
skill: claude-api
skill: workflow-authoring
skill: run
skill: plugin-authoring
skill: init
skill: security-review
SLASH COMMANDS (user-invocable skills, as listed):
slash command: /dataviz
slash command: /artifact-design
slash command: /artifact-diagramming
slash command: /artifact-capabilities
slash command: /update-config
slash command: /keybindings-help
slash command: /code-review
slash command: /simplify
slash command: /fewer-permission-prompts
slash command: /loop
slash command: /schedule
slash command: /claude-api
slash command: /workflow-authoring
slash command: /run
slash command: /plugin-authoring
slash command: /init
slash command: /security-review
SUBAGENTS:
subagent: claude
subagent: claude-code-guide
subagent: Explore
subagent: general-purpose
subagent: Plan
subagent: statusline-setup
PLUGINS: none visible
MCP SERVERS: none visible
HOOKS: none visible
INSTRUCTION FILES:
CLAUDE.md: none loaded/visible
memory index (referenced, contents not loaded): ~/.claude/projects/-private-var-folders-jz-bllky2897qv9q9qk5nkhpgmm0000gn-T-aci--mvodcre/memory/MEMORY.md

```

## 남는 한계

- doctor는 에이전트의 자기 보고에 의존한다. 보이지 않게 주입된 항목은 못 잡는다.
- 실행마다 `~/.claude/projects/` 아래에 임시 폴더 이름의 빈 메모리 폴더가 생긴다(내용은 비어 있어 결과에는 영향 없음).
- codex 심판은 사용자의 codex 전역 설정(MCP 서버 등)을 읽는다. 판정에는 영향이 작지만 시작 시 오류 로그가 많다.
