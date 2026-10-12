# 창의성 도구 구현 계획

> **에이전트 작업자용:** superpowers:executing-plans(이 세션에서 직접) 또는 superpowers:subagent-driven-development로 단계별 실행. 체크박스(`- [ ]`)로 추적.

**목표:** 생각 절차 스킬과 후보 경쟁 하네스를 별도 플러그인으로 만들고, 시험 문제 48개로 늘린 벤치마크에서 Gemini 채점으로 효과를 잰다.

**구조:** 저장소 루트를 플러그인 목록(마켓플레이스)으로 바꾸고 `plugins/` 아래 두 플러그인을 둔다. 설정 파일의 `plugin:` 항목이 가리키는 폴더만 에이전트에게 준다. 점수 보고서에 평균 소요 시간과 짝 선택을 더한다.

**기술:** 기존과 같음(Python 3.11+, uv, pyyaml, pytest). 도구 본문은 마크다운 스킬·에이전트 정의.

**설계 문서:** `docs/superpowers/specs/2026-10-12-creativity-skill-design.md`

## 전체 제약

- 이 세션(도구를 만드는 쪽)은 `bench/tasks/*/` 아래 **split이 holdout인 새 태스크 내용을 읽지 않는다**. 확인은 테스트 결과와 개수로만.
- 도구 다듬기는 연습 문제(dev)로만, 도구마다 최대 3회.
- 최종 측정은 시험 문제(holdout) 48개, 문제당 2회, 세 설정, Gemini 채점, 한 번만.
- 하위 에이전트 수 3 고정, 옵션화하지 않는다.
- 성공: 시험 문제 지수의 95% 범위 아래쪽 끝 > 50.

## 검토 초점

1. `plugin:`이 없는 설정(기준 에이전트) — 빈 플러그인 폴더가 넘어가도 실행이 깨지지 않아야 한다. → 작업 1 `test_no_plugin_gives_empty_dir`
2. 한 실행 폴더에 세 설정 판정이 섞인 경우 — 고른 짝만 점수에 들어가야 한다. → 작업 2 `test_score_picks_requested_pair`
3. 소요 시간이 없는 오래된 기록 — 평균 계산이 깨지지 않아야 한다. → 작업 2 `test_average_duration`
4. 하네스가 시간 제한을 넘기는 경우 — 실패로 기록되고 다음 샘플로 넘어간다(기존 동작). 설정에서 2400초.
5. 스킬이 발동하지 않는 경우 — 연습 실행 기록에서 확인(작업 6).

---

### 작업 1: 플러그인 구조와 설정의 `plugin:` 항목

**파일:**
- 수정: `bench/aci/adapter.py`(Config에 `plugin`), `bench/aci/runner.py`(플러그인 복사), `bench/tests/test_runner.py`
- 삭제: `.claude-plugin/plugin.json`, `skills/.gitkeep`, `bench/configs/claude-skill.yaml`
- 생성: `.claude-plugin/marketplace.json`, `plugins/creative-thinking/.claude-plugin/plugin.json`, `plugins/creative-tournament/.claude-plugin/plugin.json`, `bench/configs/claude-thinking.yaml`, `bench/configs/claude-tournament.yaml`

**연결:** `Config(name, cmd, timeout=900, env={}, plugin: str | None = None)`. `run_sample`은 `repo_root / config.plugin` 폴더 내용만 `{plugin_dir}`에 복사하고, `plugin`이 없으면 빈 폴더를 넘긴다.

- [ ] **1단계: 실패하는 테스트**

`bench/tests/test_runner.py`의 `test_plugin_dir_holds_only_plugin_files`를 아래 두 테스트로 바꾸고, `load_config` 테스트를 더한다.
```python
def test_plugin_dir_holds_only_the_configured_plugin(tmp_path):
    repo = tmp_path / "repo"
    (repo / "plugins" / "p" / ".claude-plugin").mkdir(parents=True)
    (repo / "plugins" / "p" / "skills").mkdir()
    (repo / "plugins" / "q").mkdir()
    (repo / "bench").mkdir()
    cfg = Config(name="p", cmd="ls -A {plugin_dir} > {output}", plugin="plugins/p")
    run_sample(make_task(tmp_path), cfg, 0, tmp_path / "out", repo)
    listing = (sample_dir(tmp_path / "out", "t1", "p", 0) / "output" / "answer.md").read_text().split()
    assert listing == [".claude-plugin", "skills"]


def test_no_plugin_gives_empty_dir(tmp_path):
    cfg = Config(name="n", cmd="ls -A {plugin_dir} > {output}")
    run_sample(make_task(tmp_path), cfg, 0, tmp_path / "out", tmp_path)
    assert (sample_dir(tmp_path / "out", "t1", "n", 0) / "output" / "answer.md").read_text() == ""


def test_load_config_reads_plugin(tmp_path):
    path = tmp_path / "c.yaml"
    path.write_text("name: c\ncmd: echo\nplugin: plugins/p\n")
    assert load_config(path).plugin == "plugins/p"
```
(맨 위 import에 `load_config` 추가.)

- [ ] **2단계: 실패 확인** — `cd bench && uv run pytest tests/test_runner.py -q` → 새 테스트 실패

- [ ] **3단계: 구현**

`adapter.py`: `Config`에 `plugin: str | None = None` 필드 추가, `load_config`에서 `plugin=data.get("plugin")`.

`runner.py`의 플러그인 복사 부분을 바꾼다:
```python
        if config.plugin:  # only the configured plugin, never the tasks or answers
            shutil.copytree(repo_root / config.plugin, plugin_dir, dirs_exist_ok=True)
```

`.claude-plugin/marketplace.json`:
```json
{
  "name": "agent-creativity-index",
  "owner": { "name": "hesong0222-dev", "url": "https://github.com/hesong0222-dev" },
  "plugins": [
    {
      "name": "creative-thinking",
      "source": "./plugins/creative-thinking",
      "description": "A thinking procedure that steers an agent away from the obvious answer on open-ended work"
    },
    {
      "name": "creative-tournament",
      "source": "./plugins/creative-tournament",
      "description": "Three subagents build rival versions from different angles; a blind selector keeps the most original"
    }
  ]
}
```

`plugins/creative-thinking/.claude-plugin/plugin.json`:
```json
{
  "name": "creative-thinking",
  "version": "0.1.0",
  "license": "AGPL-3.0-or-later",
  "description": "A thinking procedure that steers an agent away from the obvious answer on open-ended work",
  "author": { "name": "hesong0222-dev", "url": "https://github.com/hesong0222-dev" },
  "repository": "https://github.com/hesong0222-dev/agent-creativity-index"
}
```
`plugins/creative-tournament/.claude-plugin/plugin.json`: 위와 같되 `name: creative-tournament`, 설명은 marketplace의 것.

`bench/configs/claude-thinking.yaml`:
```yaml
# Treatment 1: the baseline plus the creative-thinking plugin only.
name: claude-thinking
plugin: plugins/creative-thinking
cmd: >-
  claude -p --setting-sources project --strict-mcp-config
  --plugin-dir {plugin_dir} --dangerously-skip-permissions < {prompt_file}
timeout: 900
```
`bench/configs/claude-tournament.yaml`: 같은 모양, `name: claude-tournament`, `plugin: plugins/creative-tournament`, `timeout: 2400`.

README의 설정 예시와 자리표시자 설명을 `plugin:` 기준으로 고친다(예시 설정을 claude-thinking으로).

- [ ] **4단계: 통과 확인** — `cd bench && uv run pytest -q` → 전부 통과
- [ ] **5단계: 커밋** — `feat: per-config plugin folders and plugin marketplace layout`

### 작업 2: 보고서에 평균 소요 시간, 점수에 짝 선택

**파일:** 수정 `bench/aci/score.py`, `bench/aci/cli.py`, `bench/tests/test_score.py`

**연결:** `summarize(run_dir, tasks, n_boot=2000, seed=0, a=None, b=None)` — `a`/`b`가 주어지면 `judge.json`의 짝 대신 쓴다. `_run_stats` 각 설정에 `duration_total`, 보고서 실행 표에 `avg seconds` 열. `aci score --a NAME --b NAME`.

- [ ] **1단계: 실패하는 테스트**
```python
def test_score_picks_requested_pair(tmp_path):
    tasks = [Task("m1", "make", "holdout", "p", "o.md", tmp_path)]
    run = tmp_path / "run"
    (run / "m1").mkdir(parents=True)
    rows = [{"sample": 0, "winner": "B", "auto": False, "parse_failures": 0, "a": "x", "b": "y", "judge": "j"},
            {"sample": 0, "winner": "A", "auto": False, "parse_failures": 0, "a": "x", "b": "z", "judge": "j"}]
    (run / "m1" / "judgments.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (run / "judge.json").write_text(json.dumps({"name": "j", "cmd": "gemini", "a": "x", "b": "z"}))
    assert summarize(run, tasks, n_boot=10)["axes"]["make"]["rate"] == 0
    assert summarize(run, tasks, n_boot=10, a="x", b="y")["axes"]["make"]["rate"] == 100


def test_average_duration(tmp_path):
    tasks = [Task("m1", "make", "holdout", "p", "o.md", tmp_path)]
    for i, seconds in enumerate((10.0, 20.0)):
        d = tmp_path / "run" / "m1" / "c" / str(i)
        d.mkdir(parents=True)
        (d / "meta.json").write_text(json.dumps({"config": "c", "exit_code": 0, "timed_out": False,
                                                 "has_output": True, "passed": None, "duration": seconds}))
    s = summarize(tmp_path / "run", tasks, n_boot=10)
    assert "| c | 2 | 0 | 0 | 0 | n/a | 15.0 |" in render_markdown(s, "holdout")
```
- [ ] **2단계: 실패 확인**
- [ ] **3단계: 구현**
  - `summarize`에 `a: str | None = None, b: str | None = None` 인자. `want` 계산 뒤 `if a: want["a"] = a`, `if b: want["b"] = b`.
  - `_run_stats` 각 설정 사전에 `"duration_total": 0.0`, 합산 `s["duration_total"] += m.get("duration") or 0.0`.
  - `render_markdown` 실행 표 머리를 `| config | samples | failed | timed out | no output | solve passed | avg seconds |`, 구분선 7칸, 행 끝에 `f" {s['duration_total'] / s['samples']:.1f} |"`.
  - `cli.py` score 하위 명령에 `--a`, `--b`(선택) 추가, `summarize(..., a=args.a, b=args.b)`. `report.json`에 `"a"`, `"b"` 기록.
- [ ] **4단계: 통과 확인** — 전체 통과
- [ ] **5단계: 커밋** — `feat: average duration in report, pick pair at score time`

### 작업 3: 시험 문제 36개 추가(별도 에이전트, 이 세션은 내용 열람 금지)

**파일:** 생성 `bench/tasks/{solve,diverge,make}/<new-id>/...` × 36(별도 에이전트), 수정 `bench/tests/test_task_set.py`, `bench/tests/test_solve_tasks.py`

- [ ] **1단계: 개수 테스트 먼저 바꾸기**

`test_task_set.py`:
```python
def test_shipped_task_set_shape():
    tasks = load_tasks()
    assert len(tasks) == 60
    counts = Counter((t.axis, t.split) for t in tasks)
    assert counts == {(a, s): (4 if s == "dev" else 16) for a in AXES for s in SPLITS}
```
`test_solve_tasks.py`의 `test_eight_solve_tasks`를 `assert len(SOLVE) == 20`으로(이름 `test_twenty_solve_tasks`).

- [ ] **2단계: 실패 확인** — 두 테스트 실패

- [ ] **3단계: 별도 에이전트에게 작성 위임**

일반 목적 에이전트(Opus)에 아래를 지시한다. 보고에는 **태스크 내용·주제를 쓰지 말고** 만든 개수, 테스트 결과 줄만 쓰게 한다.

> 저장소 `<repo>/bench/tasks/`에 split이 `holdout`인 새 태스크를 축마다 12개씩(solve 12, diverge 12, make 12) 만든다. 형식은 같은 축의 기존 dev 태스크(`split: dev`인 것)를 그대로 따른다. 기존 holdout 태스크는 열지 마라. 원칙: 기존 dev·holdout과 주제가 겹치지 않을 것(dev 태스크 목록만 참고), 특정 모델·스킬에 유리한 표현 금지, 결과물이 한 화면 분량.
> - solve: 각 태스크에 `task.yaml`(output `solution.py`, check `"{python} -m pytest -q tests"`, 프롬프트에 규칙 목록과 `no eval, exec, compile, getattr, setattr, __import__, globals, locals, vars, or open` 줄 포함), `starter/solution.py`(NotImplementedError), `tests/test_solution.py`(기존과 같은 머리말 + 규칙 검사 + 동작 검사 + `test_no_dynamic_code`), `reference.py`(규칙을 지키는 정답), `obvious.py`(동작은 맞지만 규칙을 어기는 흔한 풀이). 흔한 풀이를 규칙으로 막되 다른 정답이 여러 갈래 있도록.
> - diverge: 10개 목록 형식, 기존 dev와 같은 마지막 문단.
> - make: 요구사항 2~3개를 명시한 창작물(이야기, 단일 HTML 게임/페이지, 형식이 정해진 글 등을 섞어서).
> - id는 축 이름으로 시작하고 기존 id와 겹치지 않게.
> - 끝나면 `cd bench && uv run pytest -q`가 모두 통과해야 한다. 실패하면 태스크를 고쳐라(규칙을 느슨하게 해서 obvious가 통과하게 두지 말 것).
> - 커밋: `git add bench/tasks && git commit -m "feat: 36 new holdout tasks"`.
> - 보고: 만든 개수(축별), 마지막 pytest 요약 한 줄. 태스크 내용과 주제는 보고에 쓰지 마라.

- [ ] **4단계: 확인** — 이 세션은 `cd bench && uv run pytest -q 2>&1 | tail -1`만 본다 → 전부 통과. `git show --stat HEAD | tail -1`로 파일 수만 확인.
- [ ] **5단계: 커밋** — 테스트 파일 변경 `test: 60-task set shape`

### 작업 4: 생각 절차 스킬

**파일:** 생성 `plugins/creative-thinking/skills/creative-thinking/SKILL.md`

- [ ] **1단계: 작성**
```markdown
---
name: creative-thinking
description: Use for open-ended work where many answers are valid — generating ideas, writing stories or poems, designing pages or games, or solving a problem under constraints that rule out the usual approach. Steers away from the first obvious answer before committing.
---

# Creative thinking

Your first idea is usually everyone's first idea. Before you build anything, spend a minute leaving it behind.

1. **Pin the requirements.** Write each hard requirement of the task as one short line (length, format, file name, rules you must not break). You will check against this list at the end.
2. **Name the obvious.** Write the three answers most people would give first. You will not build any of them, nor anything in the same direction.
3. **Sketch distant directions.** Sketch 3 to 5 candidates in one or two lines each, every one reached by a different move:
   - borrow a mechanism from an unrelated field
   - invert a premise the task quietly assumes
   - add a constraint that forces an unusual shape
   - change the point of view (narrator, user, material, time scale)
4. **Choose.** Keep the candidate that meets every requirement and is least like the obvious answers. Note in one line why it is less obvious.
5. **Build it fully.** Commit to the chosen direction; do not drift back toward the obvious while executing.
6. **Check the requirements.** Go through the list from step 1, line by line. If anything is broken, fix it — a requirement beats an idea.

Keep steps 1–4 in your head or scratch notes, never in the deliverable. For lists of ideas, apply step 2 to each item and make the items differ from each other in kind, not just in wording.
```
- [ ] **2단계: 형식 확인** — `cd bench && uv run aci doctor configs/claude-thinking.yaml` → PASS, 인벤토리에 `creative-thinking` 이 보임
- [ ] **3단계: 커밋** — `feat: creative-thinking skill`

### 작업 5: 후보 경쟁 하네스

**파일:** 생성 `plugins/creative-tournament/skills/creative-tournament/SKILL.md`, `plugins/creative-tournament/agents/explorer.md`, `plugins/creative-tournament/agents/selector.md`

- [ ] **1단계: 작성**

`SKILL.md`:
```markdown
---
name: creative-tournament
description: Use for open-ended work where many answers are valid — generating ideas, writing stories or poems, designing pages or games, or solving a problem under constraints that rule out the usual approach. Runs three rival builds from different angles and keeps the most original one that meets every requirement.
---

# Creative tournament

1. **Pin the requirements.** Write each hard requirement of the task as one line in `.tournament/requirements.md` (create the folder in the current directory).
2. **Launch three explorers at once.** Start three `explorer` subagents in parallel, in a single message. Give each the full task text, the requirements file path, its own output folder (`.tournament/a`, `.tournament/b`, `.tournament/c`) and one angle:
   - a: borrow a mechanism from an unrelated field
   - b: invert a premise the task quietly assumes
   - c: add a constraint that forces an unusual shape
   Each explorer writes a complete deliverable, under the task's required file name, inside its own folder.
3. **Select blind.** Start one `selector` subagent with the task text, the requirements file, and the three folders. It returns the letter of the winner.
4. **Deliver.** Copy the winner's deliverable to the location the task asks for. Check every requirement once more and fix anything broken. Delete `.tournament/`.

If an explorer fails, select among the ones that finished. If all fail, do the task yourself.
```

`agents/explorer.md`:
```markdown
---
name: explorer
description: Builds one complete, deliberately unusual version of a deliverable from an assigned angle, inside an assigned folder.
---

You build one complete version of the deliverable described in the task, from the angle you were given.

- Read the task text and the requirements file you were given.
- Write down (privately) the three answers most people would give first, and stay away from their direction.
- Let your assigned angle drive the core idea, not just decoration.
- Write the full deliverable, under the task's required file name, inside your assigned folder only. Do not touch anything else.
- Before finishing, check every requirement line. A requirement beats an idea.
- Reply with one line: the file you wrote.
```

`agents/selector.md`:
```markdown
---
name: selector
description: Compares candidate deliverables blind and picks the most original one that meets every requirement.
---

You choose one winner among candidate deliverables in the folders you were given.

1. Read the task text and the requirements file.
2. Drop any candidate that breaks a requirement. If all break one, keep those that break the fewest.
3. Among the rest, pick the one that is most original — least like what most people would produce first — while still being good work. Do not reward length.
4. Reply with only the folder letter of the winner and one sentence of reason, like `b: ...`.
```
- [ ] **2단계: 형식 확인** — `uv run aci doctor configs/claude-tournament.yaml` → PASS, `creative-tournament`와 하위 에이전트 두 개가 보임
- [ ] **3단계: 커밋** — `feat: creative-tournament harness`

### 작업 6: 연습 문제로 다듬기(도구마다 최대 3회)

**파일:** 생성 `docs/results/2026-10-12-dev-iterations.md`

- [ ] **1단계: 실행** (백그라운드)
```bash
cd bench && uv run aci run --config configs/claude-base.yaml --config configs/claude-thinking.yaml --config configs/claude-tournament.yaml --split dev -k 2 -j 3 --out runs/dev-r1
```
- [ ] **2단계: 발동 확인** — 각 도구 설정의 `stdout.txt`·결과물에서 스킬을 따랐는지(하네스는 `.tournament` 흔적이 없어야 하고 결과물이 있어야 함), 시간 초과·실패 수 확인. 하위 에이전트가 동작하지 않으면 멈추고 사용자에게 보고.
- [ ] **3단계: 채점과 점수**(연습은 Claude 채점기)
```bash
cd bench && uv run aci judge runs/dev-r1 --a claude-base --b claude-thinking --judge configs/judge-claude.yaml -j 3
cd bench && uv run aci judge runs/dev-r1 --a claude-base --b claude-tournament --judge configs/judge-claude.yaml -j 3
cd bench && uv run aci score runs/dev-r1 --split dev --a claude-base --b claude-thinking
cd bench && uv run aci score runs/dev-r1 --split dev --a claude-base --b claude-tournament
```
- [ ] **4단계: 다듬기 판단** — 지는 축의 채점 이유를 읽고, 도구 문구를 고칠 근거가 있으면 고치고 `runs/dev-r2`로 다시(최대 r3). 매 회 결과와 고친 이유를 `docs/results/2026-10-12-dev-iterations.md`에 기록. 근거 없이 점수를 쫓아 고치지 않는다.
- [ ] **5단계: 커밋** — 도구 수정과 기록

### 작업 7: 최종 측정(시험 문제, Gemini 채점, 한 번)

**파일:** 생성 `docs/results/2026-10-12-final-holdout.md`, 수정 `README.md`

- [ ] **1단계: Gemini 채점기 확인** — `call_judge(load_config('configs/judge-gemini.yaml'), ...)` 가 `'1'`을 돌려줘야 한다. 안 되면 멈추고 사용자에게 알림.
- [ ] **2단계: 실행** (백그라운드, 오래 걸림)
```bash
cd bench && uv run aci run --config configs/claude-base.yaml --config configs/claude-thinking.yaml --config configs/claude-tournament.yaml --split holdout -k 2 -j 3 --out runs/final
```
- [ ] **3단계: 채점·점수**
```bash
cd bench && uv run aci judge runs/final --a claude-base --b claude-thinking --judge configs/judge-gemini.yaml -j 3
cd bench && uv run aci judge runs/final --a claude-base --b claude-tournament --judge configs/judge-gemini.yaml -j 3
cd bench && uv run aci score runs/final --split holdout --a claude-base --b claude-thinking
cd bench && uv run aci score runs/final --split holdout --a claude-base --b claude-tournament
```
- [ ] **4단계: 기록** — 두 보고서를 `docs/results/2026-10-12-final-holdout.md`에 싣고, 맨 위에 조건(버전, k, 채점기, 날짜)과 도구별 성공/실패 판정(범위 아래쪽 끝 > 50?), 평균 소요 시간 비교, 테스트 통과율을 적는다. README에 결과 요약 절과 설치 방법(`/plugin marketplace add hesong0222-dev/agent-creativity-index`)을 더한다.
- [ ] **5단계: 커밋·공개** — 커밋 후 `git push`. 결과가 실패여도 그대로 공개.
