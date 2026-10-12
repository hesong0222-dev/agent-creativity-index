# ACI 벤치마크 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 스킬을 켠 에이전트(B)와 끈 에이전트(A)를 같은 24개 태스크로 돌리고, 다른 계열 모델이 블라인드 쌍대 비교로 판정해 "창의성 지수"(50 = 차이 없음)를 내는 CLI `aci`를 만든다.

**Architecture:** `bench/aci/` 안에 책임별 작은 모듈 — `tasks`(태스크 로드), `adapter`(명령어 템플릿 실행), `runner`(격리 작업 폴더에서 에이전트 실행), `judge`(순서 바꿈 이중 판정), `score`(승률·부트스트랩·지수), `doctor`(격리 검사), `cli`. 결과는 전부 `runs/<name>/` 아래 파일로 남고, 각 단계는 이미 끝난 것을 건너뛰어 재개된다.

**Tech Stack:** Python ≥ 3.11, uv, pyyaml, pytest. 그 밖은 표준 라이브러리.

**Spec:** `docs/superpowers/specs/2026-10-12-benchmark-design.md`

## Global Constraints

- Python ≥ 3.11. 런타임 의존성은 `pyyaml`, `pytest` 둘뿐(pytest는 solve 축 채점에 쓰이므로 런타임 의존성).
- 모든 명령은 `bench/`에서 `uv run aci ...`, `uv run pytest ...`로 실행한다.
- 태스크 프롬프트, README, 코드 주석은 영어. 설계·계획 문서는 한국어.
- 라이선스 AGPL-3.0-or-later. 플러그인 이름 `agent-creativity-index`.
- 에이전트 명령은 매번 새 임시 작업 폴더에서만 실행. `tests/`는 에이전트가 끝난 뒤에만 복사.
- 축별 B 승률 = (B 승 + ½ 무승부) / 짝 수 × 100. 지수 = 판정이 있는 축 승률의 평균. 부트스트랩 2,000회, 시드 0, 축 안에서 태스크 단위 재표집.
- 판정은 순서를 바꿔 두 번. 두 판정이 같은 쪽이어야 승, 아니면 무승부.
- `aci score` 기본 split은 `holdout`.
- 기본 심판은 codex(피평가 Claude와 다른 계열).

## Review Focus

1. 결과물이 폴더이거나 하위 경로(`site/css/a.css`)인 경우 — 그대로 복사돼야 한다. → Task 2 `test_run_sample_copies_nested_directory_output`
2. 결과물에 바이너리 파일이나 3만 자 넘는 텍스트가 섞인 경우 — 심판 프롬프트가 깨지거나 폭주하지 않아야 한다. → Task 3 `test_read_output_skips_binary_and_truncates`
3. 심판이 JSON을 설명문·코드펜스로 감싸거나 winner를 문자열 `"2"`/`"TIE"`로 주는 경우 — 정상 판정으로 읽혀야 한다. → Task 3 `test_parse_verdict_variants`
4. 실행이 중간에 끊겨 `meta.json` 없는 샘플 폴더가 남은 경우 — 재실행 시 깨끗하게 다시 돌아야 한다. → Task 2 `test_resume_skips_finished_and_reruns_partial`
5. 특정 축이나 split에 판정이 하나도 없는 경우(예: dev만 돌리고 holdout 점수 요청) — 0으로 나누지 않고 n/a와 경고를 내야 한다. → Task 4 `test_summarize_with_missing_axis_and_family_warning`, `test_summarize_empty`

---

### Task 1: 뼈대와 태스크 로더

**Files:**
- Create: `bench/pyproject.toml`, `bench/aci/__init__.py`, `bench/aci/tasks.py`, `bench/tests/test_tasks.py`
- Create: `.gitignore`, `.claude-plugin/plugin.json`, `skills/.gitkeep`

**Interfaces:**
- Produces: `AXES = ("solve", "diverge", "make")`, `SPLITS = ("dev", "holdout")`, `TASKS_ROOT: Path`(= `bench/tasks`), `class TaskError(ValueError)`, `@dataclass(frozen=True) Task(id, axis, split, prompt, output, dir: Path, check: str | None = None, judge_focus: str = "")`, `load_task(path: Path) -> Task`, `load_tasks(root: Path = TASKS_ROOT, split: str | None = None) -> list[Task]`(id순 정렬)

- [ ] **Step 1: 뼈대 파일 작성**

`bench/pyproject.toml`:
```toml
[project]
name = "aci"
version = "0.1.0"
description = "Agent Creativity Index"
requires-python = ">=3.11"
license = "AGPL-3.0-or-later"
dependencies = ["pyyaml>=6", "pytest>=8"]

[project.scripts]
aci = "aci.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["aci"]

[tool.pytest.ini_options]
testpaths = ["tests"]  # tasks/*/tests are run per sample by the runner, not collected here
```

`bench/aci/__init__.py`: 빈 파일.

`.gitignore`:
```
bench/runs/
bench/.claude-isolated/
.venv/
__pycache__/
*.pyc
.DS_Store
```

`.claude-plugin/plugin.json`:
```json
{
  "name": "agent-creativity-index",
  "version": "0.1.0",
  "license": "AGPL-3.0-or-later",
  "description": "Agent Creativity Index: a benchmark and a creativity skill for coding agents",
  "author": { "name": "hesong0222-dev", "url": "https://github.com/hesong0222-dev" },
  "repository": "https://github.com/hesong0222-dev/agent-creativity-index"
}
```

`skills/.gitkeep`: 빈 파일.

- [ ] **Step 2: 실패하는 테스트 작성**

`bench/tests/test_tasks.py`:
```python
from pathlib import Path

import pytest

from aci.tasks import TaskError, load_task, load_tasks

VALID = """id: t1
axis: diverge
split: dev
prompt: List ideas.
output: ideas.md
"""


def write(dir: Path, text: str) -> Path:
    dir.mkdir(parents=True, exist_ok=True)
    path = dir / "task.yaml"
    path.write_text(text)
    return path


def test_load_valid_task(tmp_path):
    task = load_task(write(tmp_path / "diverge" / "t1", VALID))
    assert (task.id, task.axis, task.split, task.output, task.check) == ("t1", "diverge", "dev", "ideas.md", None)
    assert task.dir == tmp_path / "diverge" / "t1"


@pytest.mark.parametrize("text, message", [
    (VALID.replace("output: ideas.md\n", ""), "missing 'output'"),
    (VALID.replace("axis: diverge", "axis: vibes"), "unknown axis"),
    (VALID.replace("split: dev", "split: test"), "unknown split"),
    (VALID.replace("axis: diverge", "axis: solve"), "needs 'check'"),
])
def test_invalid_task_rejected(tmp_path, text, message):
    with pytest.raises(TaskError, match=message):
        load_task(write(tmp_path / "x" / "t1", text))


def test_load_tasks_filters_split_and_rejects_duplicates(tmp_path):
    write(tmp_path / "diverge" / "a", VALID)
    write(tmp_path / "diverge" / "b", VALID.replace("id: t1", "id: t2").replace("split: dev", "split: holdout"))
    assert [t.id for t in load_tasks(tmp_path, split="holdout")] == ["t2"]
    write(tmp_path / "make" / "c", VALID)
    with pytest.raises(TaskError, match="duplicate"):
        load_tasks(tmp_path)
```

- [ ] **Step 3: 실패 확인**

Run: `cd bench && uv run pytest tests/test_tasks.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'aci.tasks'`

- [ ] **Step 4: 구현**

`bench/aci/tasks.py`:
```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

AXES = ("solve", "diverge", "make")
SPLITS = ("dev", "holdout")
TASKS_ROOT = Path(__file__).resolve().parent.parent / "tasks"


class TaskError(ValueError):
    pass


@dataclass(frozen=True)
class Task:
    id: str
    axis: str
    split: str
    prompt: str
    output: str
    dir: Path
    check: str | None = None
    judge_focus: str = ""


def load_task(path: Path) -> Task:
    data = yaml.safe_load(path.read_text()) or {}
    for key in ("id", "axis", "split", "prompt", "output"):
        if not data.get(key):
            raise TaskError(f"{path}: missing '{key}'")
    if data["axis"] not in AXES:
        raise TaskError(f"{path}: unknown axis '{data['axis']}'")
    if data["split"] not in SPLITS:
        raise TaskError(f"{path}: unknown split '{data['split']}'")
    if data["axis"] == "solve" and not data.get("check"):
        raise TaskError(f"{path}: solve task needs 'check'")
    return Task(id=data["id"], axis=data["axis"], split=data["split"], prompt=data["prompt"],
                output=data["output"], dir=path.parent, check=data.get("check"),
                judge_focus=data.get("judge_focus", ""))


def load_tasks(root: Path = TASKS_ROOT, split: str | None = None) -> list[Task]:
    tasks = [load_task(p) for p in sorted(root.glob("*/*/task.yaml"))]
    seen: set[str] = set()
    for task in tasks:
        if task.id in seen:
            raise TaskError(f"duplicate task id '{task.id}'")
        seen.add(task.id)
    if split:
        tasks = [t for t in tasks if t.split == split]
    return sorted(tasks, key=lambda t: t.id)
```

- [ ] **Step 5: 통과 확인**

Run: `cd bench && uv run pytest tests/test_tasks.py -v`
Expected: 6 passed

- [ ] **Step 6: 커밋**

```bash
git add .gitignore .claude-plugin skills bench/pyproject.toml bench/uv.lock bench/aci bench/tests
git commit -m "feat: project skeleton and task loader"
```

---

### Task 2: 어댑터와 러너

**Files:**
- Create: `bench/aci/adapter.py`, `bench/aci/runner.py`, `bench/tests/test_runner.py`

**Interfaces:**
- Consumes: `Task` (Task 1)
- Produces:
  - `adapter.py`: `@dataclass(frozen=True) Config(name: str, cmd: str, timeout: int = 900, env: dict[str, str] = {})`, `load_config(path: Path) -> Config`, `render(template: str, values: dict[str, str], quote: bool = True) -> str`, `run_shell(config: Config, values: dict[str, str], cwd: Path) -> tuple[int | None, str, str, bool]` (exit_code, stdout, stderr, timed_out)
  - `runner.py`: `sample_dir(out: Path, task_id: str, config_name: str, i: int) -> Path`, `run_check(task: Task, workdir: Path) -> bool`, `run_sample(task, config, i, out, repo_root) -> dict`, `run_all(tasks, configs, k, out, repo_root, jobs=1, log=print) -> list[dict]`
  - 샘플 폴더 내용: `prompt.md`, `stdout.txt`, `stderr.txt`, `output/<task.output>`, `meta.json` = `{"task", "config", "sample", "exit_code", "timed_out", "duration", "has_output", "passed"}` (`passed`는 solve 축만 bool, 그 외 null)
  - `runs/<name>/configs.json` = `{config_name: cmd}`
  - 템플릿 자리표시자: `{prompt_file}`, `{workdir}`, `{repo_root}`, `{output}`; check 명령은 `{python}`

- [ ] **Step 1: 실패하는 테스트 작성**

`bench/tests/test_runner.py`:
```python
from aci.adapter import Config, render, run_shell
from aci.runner import run_sample, sample_dir
from aci.tasks import Task


def make_task(tmp_path, output="answer.md", axis="make", check=None):
    d = tmp_path / "task"
    d.mkdir(exist_ok=True)
    return Task(id="t1", axis=axis, split="dev", prompt="hello prompt", output=output, dir=d, check=check)


def test_render_quotes_values():
    assert render("cat {f}", {"f": "a b.md"}) == "cat 'a b.md'"
    assert render("{f}", {"f": "a b"}, quote=False) == "a b"


def test_run_shell_times_out(tmp_path):
    code, out, err, timed_out = run_shell(Config(name="s", cmd="sleep 5", timeout=1), {}, tmp_path)
    assert timed_out and code is None


def test_run_sample_writes_output_and_meta(tmp_path):
    meta = run_sample(make_task(tmp_path), Config(name="echo", cmd="cat {prompt_file} > {output}"), 0, tmp_path / "out", tmp_path)
    d = sample_dir(tmp_path / "out", "t1", "echo", 0)
    assert meta["has_output"] and meta["exit_code"] == 0 and meta["passed"] is None
    assert (d / "output" / "answer.md").read_text() == "hello prompt"


def test_run_sample_copies_nested_directory_output(tmp_path):
    task = make_task(tmp_path, output="site")
    run_sample(task, Config(name="echo", cmd="mkdir -p site/css && echo hi > site/css/a.css"), 0, tmp_path / "out", tmp_path)
    copied = sample_dir(tmp_path / "out", "t1", "echo", 0) / "output" / "site" / "css" / "a.css"
    assert copied.read_text() == "hi\n"


def test_missing_output_recorded(tmp_path):
    meta = run_sample(make_task(tmp_path), Config(name="noop", cmd="true"), 0, tmp_path / "out", tmp_path)
    assert meta["has_output"] is False


def test_resume_skips_finished_and_reruns_partial(tmp_path):
    task = make_task(tmp_path)
    counter = tmp_path / "count"
    cfg = Config(name="c", cmd="echo x >> " + str(counter) + " && echo ok > {output}")
    out = tmp_path / "out"
    run_sample(task, cfg, 0, out, tmp_path)
    run_sample(task, cfg, 0, out, tmp_path)
    assert counter.read_text().count("x") == 1
    partial = sample_dir(out, "t1", "c", 1)
    partial.mkdir(parents=True)
    (partial / "stdout.txt").write_text("stale")
    meta = run_sample(task, cfg, 1, out, tmp_path)
    assert meta["has_output"] and (partial / "stdout.txt").read_text() == ""
    assert counter.read_text().count("x") == 2


def test_tests_are_hidden_while_agent_runs(tmp_path):
    task = make_task(tmp_path)
    (task.dir / "tests").mkdir()
    (task.dir / "starter").mkdir()
    (task.dir / "starter" / "given.txt").write_text("x")
    run_sample(task, Config(name="ls", cmd="ls > {output}"), 0, tmp_path / "out", tmp_path)
    listing = (sample_dir(tmp_path / "out", "t1", "ls", 0) / "output" / "answer.md").read_text()
    assert "given.txt" in listing and "tests" not in listing


def test_solve_check_uses_hidden_tests(tmp_path):
    task = make_task(tmp_path, output="solution.py", axis="solve", check="{python} -m pytest -q tests")
    (task.dir / "tests").mkdir()
    (task.dir / "tests" / "test_s.py").write_text("import solution\n\n\ndef test_v():\n    assert solution.V == 1\n")
    good = run_sample(task, Config(name="good", cmd="echo 'V = 1' > solution.py"), 0, tmp_path / "out", tmp_path)
    bad = run_sample(task, Config(name="bad", cmd="echo 'V = 2' > solution.py"), 0, tmp_path / "out", tmp_path)
    assert good["passed"] is True and bad["passed"] is False
```

- [ ] **Step 2: 실패 확인**

Run: `cd bench && uv run pytest tests/test_runner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'aci.adapter'`

- [ ] **Step 3: 구현**

`bench/aci/adapter.py`:
```python
from __future__ import annotations

import os
import shlex
import signal
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Config:
    name: str
    cmd: str
    timeout: int = 900
    env: dict[str, str] = field(default_factory=dict)


def load_config(path: Path) -> Config:
    data = yaml.safe_load(Path(path).read_text()) or {}
    if not data.get("name") or not data.get("cmd"):
        raise ValueError(f"{path}: config needs 'name' and 'cmd'")
    env = {k: str(v) for k, v in (data.get("env") or {}).items()}
    return Config(name=data["name"], cmd=data["cmd"], timeout=int(data.get("timeout", 900)), env=env)


def render(template: str, values: dict[str, str], quote: bool = True) -> str:
    """Fill {key} placeholders. Shell commands get quoted values; env values do not."""
    for key, value in values.items():
        template = template.replace("{" + key + "}", shlex.quote(str(value)) if quote else str(value))
    return template


def run_shell(config: Config, values: dict[str, str], cwd: Path) -> tuple[int | None, str, str, bool]:
    """Run config.cmd in cwd; on timeout kill the whole process group."""
    env = {**os.environ, **{k: render(v, values, quote=False) for k, v in config.env.items()}}
    proc = subprocess.Popen(render(config.cmd, values), shell=True, cwd=cwd, env=env, text=True,
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            start_new_session=True)
    try:
        out, err = proc.communicate(timeout=config.timeout)
        return proc.returncode, out, err, False
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        out, err = proc.communicate()
        return None, out, err, True
```

`bench/aci/runner.py`:
```python
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .adapter import Config, render, run_shell
from .tasks import Task

CHECK_TIMEOUT = 300


def sample_dir(out: Path, task_id: str, config_name: str, i: int) -> Path:
    return out / task_id / config_name / str(i)


def run_check(task: Task, workdir: Path) -> bool:
    """Copy the hidden tests into workdir and run the task's check command."""
    if (task.dir / "tests").is_dir():
        shutil.copytree(task.dir / "tests", workdir / "tests", dirs_exist_ok=True)
    cmd = render(task.check, {"python": sys.executable})
    try:
        proc = subprocess.run(cmd, shell=True, cwd=workdir, capture_output=True, timeout=CHECK_TIMEOUT)
    except subprocess.TimeoutExpired:
        return False
    return proc.returncode == 0


def run_sample(task: Task, config: Config, i: int, out: Path, repo_root: Path) -> dict:
    d = sample_dir(out, task.id, config.name, i)
    meta_path = d / "meta.json"
    if meta_path.exists():
        return json.loads(meta_path.read_text())
    if d.exists():
        shutil.rmtree(d)  # leftover from an interrupted run
    d.mkdir(parents=True)
    prompt_file = d / "prompt.md"
    prompt_file.write_text(task.prompt)
    workdir = Path(tempfile.mkdtemp(prefix="aci-"))
    try:
        if (task.dir / "starter").is_dir():
            shutil.copytree(task.dir / "starter", workdir, dirs_exist_ok=True)
        values = {"prompt_file": str(prompt_file.resolve()), "workdir": str(workdir),
                  "repo_root": str(repo_root.resolve()), "output": task.output}
        start = time.monotonic()
        exit_code, stdout, stderr, timed_out = run_shell(config, values, workdir)
        duration = round(time.monotonic() - start, 1)
        (d / "stdout.txt").write_text(stdout or "")
        (d / "stderr.txt").write_text(stderr or "")
        produced = workdir / task.output
        has_output = produced.exists()
        if has_output:
            dest = d / "output" / task.output
            dest.parent.mkdir(parents=True, exist_ok=True)
            if produced.is_dir():
                shutil.copytree(produced, dest)
            else:
                shutil.copy2(produced, dest)
        passed = (has_output and run_check(task, workdir)) if task.axis == "solve" else None
        meta = {"task": task.id, "config": config.name, "sample": i, "exit_code": exit_code,
                "timed_out": timed_out, "duration": duration, "has_output": has_output, "passed": passed}
        meta_path.write_text(json.dumps(meta, indent=2))
        return meta
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def run_all(tasks: list[Task], configs: list[Config], k: int, out: Path, repo_root: Path,
            jobs: int = 1, log=print) -> list[dict]:
    out.mkdir(parents=True, exist_ok=True)
    registry = out / "configs.json"
    known = json.loads(registry.read_text()) if registry.exists() else {}
    known.update({c.name: c.cmd for c in configs})
    registry.write_text(json.dumps(known, indent=2))

    def one(job):
        task, config, i = job
        meta = run_sample(task, config, i, out, repo_root)
        log(f"{task.id} {config.name} #{i}: exit={meta['exit_code']} output={meta['has_output']} passed={meta['passed']}")
        return meta

    work = [(t, c, i) for t in tasks for c in configs for i in range(k)]
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        return list(pool.map(one, work))
```

- [ ] **Step 4: 통과 확인**

Run: `cd bench && uv run pytest tests/test_runner.py -v`
Expected: 8 passed

- [ ] **Step 5: 커밋**

```bash
git add bench/aci/adapter.py bench/aci/runner.py bench/tests/test_runner.py
git commit -m "feat: command-template adapter and isolated runner"
```

---

### Task 3: 블라인드 쌍대 심판

**Files:**
- Create: `bench/aci/judge.py`, `bench/tests/test_judge.py`

**Interfaces:**
- Consumes: `Task`(Task 1), `Config`, `render`, `run_shell`(Task 2), 샘플 폴더 구조(Task 2)
- Produces: `parse_verdict(text: str) -> str | None`("1" | "2" | "tie"), `combine(first: str | None, second: str | None) -> str`("A" | "B" | "tie"; first = A를 응답 1로 보였을 때, second = B를 응답 1로 보였을 때), `auto_verdict(axis: str, meta_a: dict, meta_b: dict) -> str | None`, `read_output(sample: Path) -> str`, `build_prompt(task: Task, first: str, second: str) -> str`, `call_judge(judge: Config, prompt: str) -> tuple[str | None, str]`, `judge_pair(task, a_dir, b_dir, judge) -> dict`, `read_jsonl(path: Path) -> list[dict]`, `judge_run(run_dir, tasks, a, b, judge, jobs=1, log=print) -> list[dict]`
- 판정 기록(`runs/<name>/<task>/judgments.jsonl` 한 줄): `{"task", "axis", "a", "b", "sample": int, "winner": "A"|"B"|"tie", "auto": bool, "parse_failures": int, "raw": [str, str]}`
- `runs/<name>/judge.json` = `{"name", "cmd", "a", "b"}`
- 심판 템플릿 자리표시자: `{judge_prompt_file}`, `{verdict_file}`. `{verdict_file}`에 내용이 있으면 그것을, 없으면 stdout을 읽는다.

- [ ] **Step 1: 실패하는 테스트 작성**

`bench/tests/test_judge.py`:
```python
import json

from aci.adapter import Config
from aci.judge import auto_verdict, build_prompt, combine, judge_run, parse_verdict, read_jsonl, read_output
from aci.tasks import Task


def test_parse_verdict_variants():
    assert parse_verdict('{"winner": 1, "reason": "x"}') == "1"
    assert parse_verdict('Sure.\n```json\n{"winner": "2", "reason": "y"}\n```') == "2"
    assert parse_verdict('{"winner": "TIE"}') == "tie"
    assert parse_verdict("no json here") is None
    assert parse_verdict('{"winner": 3}') is None


def test_combine_requires_agreement_across_swaps():
    assert combine("1", "2") == "A"
    assert combine("2", "1") == "B"
    assert combine("1", "1") == "tie"  # pure position bias
    assert combine("tie", "2") == "tie"
    assert combine(None, "1") == "tie"


def meta(has_output=True, passed=None):
    return {"has_output": has_output, "passed": passed}


def test_auto_verdict():
    assert auto_verdict("make", meta(False), meta()) == "B"
    assert auto_verdict("make", meta(False), meta(False)) == "tie"
    assert auto_verdict("solve", meta(passed=True), meta(passed=False)) == "A"
    assert auto_verdict("solve", meta(passed=False), meta(passed=False)) == "tie"
    assert auto_verdict("solve", meta(passed=True), meta(passed=True)) is None
    assert auto_verdict("diverge", meta(), meta()) is None


def test_read_output_skips_binary_and_truncates(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    (out / "a.bin").write_bytes(b"\xff\xfe\x00")
    (out / "b.md").write_text("x" * 40_000)
    text = read_output(tmp_path)
    assert "[binary file omitted]" in text and text.endswith("[truncated]") and len(text) < 31_000


def test_build_prompt_contains_task_and_both_responses(tmp_path):
    task = Task(id="t", axis="make", split="dev", prompt="Write a poem.", output="p.md", dir=tmp_path)
    prompt = build_prompt(task, "first text", "second text")
    assert "Write a poem." in prompt and "RESPONSE 1" in prompt and "first text" in prompt and "second text" in prompt


def make_run(tmp_path, out_a="meh", out_b="GOOD"):
    task = Task(id="t", axis="make", split="dev", prompt="Write.", output="p.md", dir=tmp_path / "task")
    run = tmp_path / "run"
    for name, text in (("A", out_a), ("B", out_b)):
        d = run / "t" / name / "0"
        (d / "output").mkdir(parents=True)
        (d / "output" / "p.md").write_text(text)
        (d / "meta.json").write_text(json.dumps({"has_output": True, "passed": None}))
    return task, run


PICK_GOOD = ("if grep -A3 'RESPONSE 1' {judge_prompt_file} | grep -q GOOD; "
             "then echo '{\"winner\": 1}'; else echo '{\"winner\": 2}'; fi")


def test_judge_run_picks_consistent_winner_and_resumes(tmp_path):
    task, run = make_run(tmp_path)
    records = judge_run(run, [task], "A", "B", Config(name="j", cmd=PICK_GOOD), log=lambda m: None)
    assert [r["winner"] for r in records] == ["B"]
    assert judge_run(run, [task], "A", "B", Config(name="j", cmd=PICK_GOOD), log=lambda m: None) == []
    assert len(read_jsonl(run / "t" / "judgments.jsonl")) == 1
    assert json.loads((run / "judge.json").read_text())["a"] == "A"


def test_judge_reads_verdict_file_and_counts_parse_failures(tmp_path):
    task, run = make_run(tmp_path)
    file_judge = Config(name="f", cmd="echo junk; echo '{\"winner\": \"tie\"}' > {verdict_file}")
    assert judge_run(run, [task], "A", "B", file_judge, log=lambda m: None)[0]["winner"] == "tie"
    task2, run2 = make_run(tmp_path / "second")
    broken = judge_run(run2, [task2], "A", "B", Config(name="b", cmd="echo nope"), log=lambda m: None)[0]
    assert broken["winner"] == "tie" and broken["parse_failures"] == 2
```

- [ ] **Step 2: 실패 확인**

Run: `cd bench && uv run pytest tests/test_judge.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'aci.judge'`

- [ ] **Step 3: 구현**

`bench/aci/judge.py`:
```python
from __future__ import annotations

import json
import re
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .adapter import Config, run_shell
from .tasks import Task

VERDICTS = ("1", "2", "tie")
MAX_CHARS = 30_000
CRITERIA = {
    "solve": ("Both responses pass the task's hidden tests, so correctness is settled. Judge which approach "
              "is more original and less obvious: a solution a typical programmer would not reach first. "
              "Do not reward length."),
    "diverge": ("Judge which list holds ideas that are more different from each other and less obvious. "
                "Judge the ideas, not their count or length."),
    "make": ("First check the task's requirements. A response that breaks a requirement loses. If both meet "
             "them, or both break them, judge which is more novel and striking."),
}


def parse_verdict(text: str) -> str | None:
    for match in reversed(list(re.finditer(r"\{[^{}]*\}", text or ""))):
        try:
            obj = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        winner = str(obj.get("winner", "")).strip().lower()
        if winner in VERDICTS:
            return winner
    return None


def combine(first: str | None, second: str | None) -> str:
    """first: verdict with A shown as response 1. second: verdict with B shown as response 1."""
    a = {"1": "A", "2": "B"}.get(first, "tie")
    b = {"1": "B", "2": "A"}.get(second, "tie")
    return a if a == b else "tie"


def auto_verdict(axis: str, meta_a: dict, meta_b: dict) -> str | None:
    has_a, has_b = meta_a["has_output"], meta_b["has_output"]
    if not has_a or not has_b:
        return "tie" if has_a == has_b else ("A" if has_a else "B")
    if axis == "solve":
        passed_a, passed_b = bool(meta_a["passed"]), bool(meta_b["passed"])
        if passed_a != passed_b:
            return "A" if passed_a else "B"
        if not passed_a:
            return "tie"
    return None


def read_output(sample: Path) -> str:
    root = sample / "output"
    parts = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            text = "[binary file omitted]"
        parts.append(f"--- {path.relative_to(root)} ---\n{text}")
    joined = "\n".join(parts)
    return joined if len(joined) <= MAX_CHARS else joined[:MAX_CHARS] + "\n[truncated]"


def build_prompt(task: Task, first: str, second: str) -> str:
    focus = f"\n{task.judge_focus.strip()}\n" if task.judge_focus else ""
    return (
        "You are judging two responses to the same task. You do not know who produced them.\n\n"
        f"TASK:\n{task.prompt.strip()}\n\n"
        f"CRITERION:\n{CRITERIA[task.axis]}\n{focus}\n"
        f"RESPONSE 1:\n<<<\n{first}\n>>>\n\n"
        f"RESPONSE 2:\n<<<\n{second}\n>>>\n\n"
        'Reply with only a JSON object: {"winner": 1, 2, or "tie", "reason": "<one sentence>"}\n'
    )


def call_judge(judge: Config, prompt: str) -> tuple[str | None, str]:
    raw = ""
    for _ in range(2):  # one retry on an unreadable verdict
        with tempfile.TemporaryDirectory(prefix="aci-judge-") as tmp:
            prompt_file, verdict_file = Path(tmp) / "prompt.md", Path(tmp) / "verdict.txt"
            prompt_file.write_text(prompt)
            values = {"judge_prompt_file": str(prompt_file), "verdict_file": str(verdict_file)}
            _, stdout, _, _ = run_shell(judge, values, Path(tmp))
            from_file = verdict_file.read_text() if verdict_file.exists() else ""
            raw = from_file if from_file.strip() else (stdout or "")
        verdict = parse_verdict(raw)
        if verdict:
            return verdict, raw
    return None, raw


def judge_pair(task: Task, a_dir: Path, b_dir: Path, judge: Config) -> dict:
    meta_a = json.loads((a_dir / "meta.json").read_text())
    meta_b = json.loads((b_dir / "meta.json").read_text())
    record = {"sample": int(a_dir.name), "winner": None, "auto": False, "parse_failures": 0, "raw": []}
    auto = auto_verdict(task.axis, meta_a, meta_b)
    if auto:
        record.update(winner=auto, auto=True)
        return record
    out_a, out_b = read_output(a_dir), read_output(b_dir)
    first, raw_first = call_judge(judge, build_prompt(task, out_a, out_b))
    second, raw_second = call_judge(judge, build_prompt(task, out_b, out_a))
    record.update(winner=combine(first, second), parse_failures=(first is None) + (second is None),
                  raw=[raw_first[-2000:], raw_second[-2000:]])
    return record


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def judge_run(run_dir: Path, tasks: list[Task], a: str, b: str, judge: Config,
              jobs: int = 1, log=print) -> list[dict]:
    (run_dir / "judge.json").write_text(json.dumps({"name": judge.name, "cmd": judge.cmd, "a": a, "b": b}, indent=2))
    pending = []
    for task in tasks:
        a_root = run_dir / task.id / a
        if not a_root.is_dir():
            continue
        done = {r["sample"] for r in read_jsonl(run_dir / task.id / "judgments.jsonl")}
        for a_dir in sorted(a_root.iterdir(), key=lambda p: int(p.name)):
            b_dir = run_dir / task.id / b / a_dir.name
            if int(a_dir.name) in done or not (a_dir / "meta.json").exists() or not (b_dir / "meta.json").exists():
                continue
            pending.append((task, a_dir, b_dir))

    lock = threading.Lock()

    def one(item):
        task, a_dir, b_dir = item
        record = {"task": task.id, "axis": task.axis, "a": a, "b": b, **judge_pair(task, a_dir, b_dir, judge)}
        with lock, (run_dir / task.id / "judgments.jsonl").open("a") as f:
            f.write(json.dumps(record) + "\n")
        log(f"{task.id} #{record['sample']}: {record['winner']}{' (auto)' if record['auto'] else ''}")
        return record

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        return list(pool.map(one, pending))
```

- [ ] **Step 4: 통과 확인**

Run: `cd bench && uv run pytest tests/test_judge.py -v`
Expected: 7 passed

- [ ] **Step 5: 커밋**

```bash
git add bench/aci/judge.py bench/tests/test_judge.py
git commit -m "feat: blind swapped pairwise judge"
```

---

### Task 4: 점수와 보고서

**Files:**
- Create: `bench/aci/score.py`, `bench/tests/test_score.py`

**Interfaces:**
- Consumes: `AXES`, `Task`(Task 1), `read_jsonl`(Task 3), `meta.json`·`configs.json`·`judge.json`·`judgments.jsonl` 형식(Task 2·3)
- Produces: `POINTS = {"B": 1.0, "tie": 0.5, "A": 0.0}`, `win_rate(scores: list[float]) -> float | None`, `bootstrap(by_axis: dict[str, dict[str, list[float]]], n=2000, seed=0) -> tuple[dict[str, tuple[float, float]], tuple[float, float] | None]`, `family(cmd: str) -> str`, `summarize(run_dir: Path, tasks: list[Task], n_boot=2000, seed=0) -> dict`, `render_markdown(summary: dict, split: str) -> str`
- `summarize` 반환: `{"index": float | None, "index_ci": (lo, hi) | None, "axes": {axis: {"pairs", "judged", "B", "A", "tie", "parse_failures", "rate", "ci"}}, "runs": {config: {"samples", "failed", "timed_out", "no_output", "solve_samples", "solve_passed"}}, "warnings": [str]}`

- [ ] **Step 1: 실패하는 테스트 작성**

`bench/tests/test_score.py`:
```python
import json

from aci.score import bootstrap, family, render_markdown, summarize, win_rate
from aci.tasks import Task


def test_win_rate():
    assert win_rate([1.0, 0.5, 0.0]) == 50
    assert win_rate([]) is None


def test_bootstrap_is_deterministic_and_bounded():
    data = {"make": {"t1": [1.0, 1.0], "t2": [0.0, 0.5]}}
    first, second = bootstrap(data, n=500, seed=1), bootstrap(data, n=500, seed=1)
    assert first == second
    lo, hi = first[0]["make"]
    assert 0 <= lo <= 62.5 <= hi <= 100
    assert bootstrap({}) == ({}, None)


def test_family():
    assert family("claude -p x") == "claude"
    assert family("CLAUDE_CONFIG_DIR=/x /usr/bin/codex exec") == "codex"


def test_summarize_with_missing_axis_and_family_warning(tmp_path):
    tasks = [Task("m1", "make", "holdout", "p", "o.md", tmp_path), Task("d1", "diverge", "holdout", "p", "o.md", tmp_path)]
    run = tmp_path / "run"
    (run / "m1").mkdir(parents=True)
    (run / "m1" / "judgments.jsonl").write_text(
        json.dumps({"winner": "B", "auto": False, "parse_failures": 0}) + "\n"
        + json.dumps({"winner": "tie", "auto": True, "parse_failures": 0}) + "\n")
    (run / "configs.json").write_text(json.dumps({"a": "claude -p", "b": "claude -p --plugin-dir x"}))
    (run / "judge.json").write_text(json.dumps({"name": "j", "cmd": "claude -p"}))
    s = summarize(run, tasks, n_boot=100)
    assert s["axes"]["make"]["rate"] == 75 and s["axes"]["diverge"]["rate"] is None and s["index"] == 75
    assert any("no judgments" in w for w in s["warnings"])
    assert any("model family" in w for w in s["warnings"])
    md = render_markdown(s, "holdout")
    assert "Index: 75.0" in md and "n/a" in md


def test_summarize_empty(tmp_path):
    s = summarize(tmp_path, [], n_boot=10)
    assert s["index"] is None and "Index: n/a" in render_markdown(s, "dev")
```

- [ ] **Step 2: 실패 확인**

Run: `cd bench && uv run pytest tests/test_score.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'aci.score'`

- [ ] **Step 3: 구현**

`bench/aci/score.py`:
```python
from __future__ import annotations

import json
import random
import shlex
from pathlib import Path

from .judge import read_jsonl
from .tasks import AXES, Task

POINTS = {"B": 1.0, "tie": 0.5, "A": 0.0}


def win_rate(scores: list[float]) -> float | None:
    return 100 * sum(scores) / len(scores) if scores else None


def _interval(values: list[float]) -> tuple[float, float]:
    values = sorted(values)
    return values[int(0.025 * (len(values) - 1))], values[int(0.975 * (len(values) - 1))]


def bootstrap(by_axis: dict[str, dict[str, list[float]]], n: int = 2000, seed: int = 0):
    """Resample tasks with replacement inside each axis. Returns ({axis: ci}, index_ci)."""
    if not by_axis:
        return {}, None
    rng = random.Random(seed)
    axis_draws: dict[str, list[float]] = {axis: [] for axis in by_axis}
    index_draws = []
    for _ in range(n):
        rates = []
        for axis, tasks in by_axis.items():
            ids = sorted(tasks)
            rate = win_rate([s for _ in ids for s in tasks[rng.choice(ids)]])
            axis_draws[axis].append(rate)
            rates.append(rate)
        index_draws.append(sum(rates) / len(rates))
    return {axis: _interval(d) for axis, d in axis_draws.items()}, _interval(index_draws)


def family(cmd: str) -> str:
    for token in shlex.split(cmd):
        if "=" not in token:
            return Path(token).name
    return ""


def summarize(run_dir: Path, tasks: list[Task], n_boot: int = 2000, seed: int = 0) -> dict:
    by_axis: dict[str, dict[str, list[float]]] = {}
    counts = {axis: {"pairs": 0, "judged": 0, "B": 0, "A": 0, "tie": 0, "parse_failures": 0} for axis in AXES}
    for task in tasks:
        records = read_jsonl(run_dir / task.id / "judgments.jsonl")
        if not records:
            continue
        c = counts[task.axis]
        for r in records:
            c["pairs"] += 1
            c[r["winner"]] += 1
            c["judged"] += 0 if r["auto"] else 1
            c["parse_failures"] += r.get("parse_failures", 0)
        by_axis.setdefault(task.axis, {})[task.id] = [POINTS[r["winner"]] for r in records]
    axis_ci, index_ci = bootstrap(by_axis, n_boot, seed)
    axes = {}
    for axis in AXES:
        scores = [s for v in by_axis.get(axis, {}).values() for s in v]
        axes[axis] = {**counts[axis], "rate": win_rate(scores), "ci": axis_ci.get(axis)}
    rates = [a["rate"] for a in axes.values() if a["rate"] is not None]
    summary = {"index": sum(rates) / len(rates) if rates else None, "index_ci": index_ci,
               "axes": axes, "runs": _run_stats(run_dir, tasks)}
    summary["warnings"] = _warnings(run_dir, summary)
    return summary


def _run_stats(run_dir: Path, tasks: list[Task]) -> dict:
    stats: dict[str, dict] = {}
    for task in tasks:
        for meta_path in sorted((run_dir / task.id).glob("*/*/meta.json")):
            m = json.loads(meta_path.read_text())
            s = stats.setdefault(m["config"], {"samples": 0, "failed": 0, "timed_out": 0, "no_output": 0,
                                               "solve_samples": 0, "solve_passed": 0})
            s["samples"] += 1
            s["failed"] += int(m["exit_code"] != 0)
            s["timed_out"] += int(m["timed_out"])
            s["no_output"] += int(not m["has_output"])
            if m["passed"] is not None:
                s["solve_samples"] += 1
                s["solve_passed"] += int(m["passed"])
    return stats


def _warnings(run_dir: Path, summary: dict) -> list[str]:
    out = []
    missing = [axis for axis, v in summary["axes"].items() if v["pairs"] == 0]
    if missing:
        out.append(f"no judgments for axes: {', '.join(missing)}; the index averages the rest")
    for axis, v in summary["axes"].items():
        if v["judged"] and v["parse_failures"] / (2 * v["judged"]) > 0.10:
            out.append(f"{axis}: judge failures above 10% of calls")
    configs_path, judge_path = run_dir / "configs.json", run_dir / "judge.json"
    configs = json.loads(configs_path.read_text()) if configs_path.exists() else {}
    judge = json.loads(judge_path.read_text()) if judge_path.exists() else None
    if judge and family(judge["cmd"]) in {family(cmd) for cmd in configs.values()}:
        out.append(f"judge and agent share a model family ({family(judge['cmd'])}); self-preference bias possible")
    return out


def _fmt(rate: float | None, ci) -> str:
    if rate is None:
        return "n/a"
    return f"{rate:.1f} [{ci[0]:.1f}, {ci[1]:.1f}]" if ci else f"{rate:.1f}"


def render_markdown(summary: dict, split: str) -> str:
    lines = [f"# Agent Creativity Index ({split})", "",
             f"**Index: {_fmt(summary['index'], summary['index_ci'])}** (50 = no difference, above 50 = B more creative)", "",
             "| axis | B win rate [95% CI] | pairs | B | A | tie | judged | judge failures |",
             "|---|---|---|---|---|---|---|---|"]
    for axis, v in summary["axes"].items():
        lines.append(f"| {axis} | {_fmt(v['rate'], v['ci'])} | {v['pairs']} | {v['B']} | {v['A']} | {v['tie']} "
                     f"| {v['judged']} | {v['parse_failures']} |")
    lines += ["", "| config | samples | failed | timed out | no output | solve passed |", "|---|---|---|---|---|---|"]
    for name, s in summary["runs"].items():
        solve = f"{s['solve_passed']}/{s['solve_samples']}" if s["solve_samples"] else "n/a"
        lines.append(f"| {name} | {s['samples']} | {s['failed']} | {s['timed_out']} | {s['no_output']} | {solve} |")
    if summary["warnings"]:
        lines += ["", "## Warnings", ""] + [f"- {w}" for w in summary["warnings"]]
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: 통과 확인**

Run: `cd bench && uv run pytest tests/test_score.py -v`
Expected: 5 passed

- [ ] **Step 5: 커밋**

```bash
git add bench/aci/score.py bench/tests/test_score.py
git commit -m "feat: win rate, bootstrap CI, index report"
```

---

### Task 5: 격리 검사(doctor), CLI, 가짜 설정, 종단 간 연기 테스트

**Files:**
- Create: `bench/aci/doctor.py`, `bench/aci/cli.py`, `bench/configs/fake-agent.yaml`, `bench/configs/fake-judge.yaml`, `bench/tests/test_doctor.py`, `bench/tests/test_cli.py`

**Interfaces:**
- Consumes: Task 1~4의 모든 공개 함수
- Produces: `doctor.py`: `OWN_PLUGIN = "agent-creativity-index"`, `BUILTIN_NAMES: set[str]`, `DOCTOR_PROMPT: str`, `default_forbid(home: Path | None = None) -> list[str]`, `find_hits(inventory: str, forbid: list[str]) -> list[str]`, `doctor(config: Config, repo_root: Path, forbid: list[str]) -> tuple[list[str], str]`; `cli.py`: `main(argv: list[str] | None = None) -> int`, `REPO_ROOT`; 하위 명령 `run`, `judge`, `score`, `doctor` (옵션은 아래 코드 그대로)

- [ ] **Step 1: 가짜 설정 작성**

`bench/configs/fake-agent.yaml`:
```yaml
# Zero-cost self-test agent: copies the prompt into the expected output file.
name: fake-agent
cmd: mkdir -p "$(dirname {output})" && cp {prompt_file} {output}
timeout: 30
```

`bench/configs/fake-judge.yaml`:
```yaml
# Zero-cost self-test judge: always prefers response 1, so swapped judging yields ties.
name: fake-judge
cmd: >-
  echo '{"winner": 1, "reason": "always picks the first response"}'
timeout: 30
```

- [ ] **Step 2: 실패하는 테스트 작성**

`bench/tests/test_doctor.py`:
```python
import json

from aci.adapter import Config
from aci.doctor import default_forbid, doctor, find_hits


def test_default_forbid_collects_user_level_items(tmp_path):
    claude = tmp_path / ".claude"
    (claude / "plugins").mkdir(parents=True)
    (claude / "plugins" / "installed_plugins.json").write_text(json.dumps({"version": 2, "plugins": {
        "superpowers@x": [], "code-review@x": [], "agent-creativity-index@y": []}}))
    (claude / "skills" / "factchk").mkdir(parents=True)
    (claude / "agents").mkdir()
    (claude / "agents" / "oxalpha-planner.md").write_text("x")
    forbid = default_forbid(home=tmp_path)
    assert {"superpowers", "factchk", "oxalpha-planner", "code-review:"} <= set(forbid)
    assert "agent-creativity-index" not in forbid and "code-review" not in forbid  # built-in name
    assert str(claude / "CLAUDE.md") in forbid


def test_find_hits_matches_whole_names_only():
    assert find_hits("Loaded: SuperPowers skill", ["superpowers", "omc"]) == ["superpowers"]
    assert find_hits("a gossip column", ["sip"]) == []
    assert find_hits("- code-review (built-in)", ["code-review:"]) == []
    assert find_hits("- code-review:code-review", ["code-review:"]) == ["code-review:"]
    assert find_hits("read /home/u/.claude/CLAUDE.md\n", ["/home/u/.claude/CLAUDE.md"]) == ["/home/u/.claude/CLAUDE.md"]


def test_doctor_with_fake_agent(tmp_path):
    hits, inventory = doctor(Config(name="fake", cmd="echo 'skills: none' > {output}"), tmp_path, ["superpowers"])
    assert hits == [] and "skills: none" in inventory
```

`bench/tests/test_cli.py`:
```python
import json
from pathlib import Path

from aci.cli import main

CONFIGS = Path(__file__).resolve().parents[1] / "configs"


def test_smoke_run_judge_score(tmp_path):
    tasks = tmp_path / "tasks"
    for axis in ("solve", "diverge", "make"):
        d = tasks / axis / f"{axis}-1"
        d.mkdir(parents=True)
        check = "check: '{python} -m pytest -q tests'\n" if axis == "solve" else ""
        (d / "task.yaml").write_text(f"id: {axis}-1\naxis: {axis}\nsplit: dev\nprompt: Do it.\noutput: answer.md\n{check}")
    fake_b = tmp_path / "fake-b.yaml"
    fake_b.write_text((CONFIGS / "fake-agent.yaml").read_text().replace("name: fake-agent", "name: fake-agent-b"))
    out = tmp_path / "run"
    assert main(["run", "--config", str(CONFIGS / "fake-agent.yaml"), "--config", str(fake_b),
                 "-k", "2", "--out", str(out), "--tasks-dir", str(tasks)]) == 0
    assert main(["judge", str(out), "--a", "fake-agent", "--b", "fake-agent-b",
                 "--judge", str(CONFIGS / "fake-judge.yaml"), "--tasks-dir", str(tasks)]) == 0
    assert main(["score", str(out), "--split", "dev", "--tasks-dir", str(tasks)]) == 0
    report = json.loads((out / "report.json").read_text())
    assert report["index"] == 50.0
    assert report["axes"]["solve"]["pairs"] == 2
    assert (out / "report.md").read_text().startswith("# Agent Creativity Index (dev)")
```

- [ ] **Step 3: 실패 확인**

Run: `cd bench && uv run pytest tests/test_doctor.py tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'aci.doctor'`

- [ ] **Step 4: 구현**

`bench/aci/doctor.py`:
```python
from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

from .adapter import Config
from .runner import run_sample, sample_dir
from .tasks import Task

OWN_PLUGIN = "agent-creativity-index"
# Names Claude Code also ships as built-ins; for these only the plugin-namespaced form ("name:") is a leak.
BUILTIN_NAMES = {"code-review", "security-review", "simplify", "init", "review"}
DOCTOR_PROMPT = (
    "List everything loaded into this session that you can see: skills, plugins, slash commands, "
    "subagents, MCP servers, hooks, and instruction files such as CLAUDE.md (give full paths). "
    "Write the list, one item per line, to inventory.txt in the current directory. Do nothing else."
)


def default_forbid(home: Path | None = None) -> list[str]:
    """Markers of the user's global setup that must not show up in an isolated session."""
    claude = (home or Path.home()) / ".claude"
    markers = ["~/.claude/CLAUDE.md", str(claude / "CLAUDE.md")]
    names: set[str] = set()
    registry = claude / "plugins" / "installed_plugins.json"
    if registry.exists():
        names |= {name.split("@")[0] for name in json.loads(registry.read_text()).get("plugins", {})}
    names |= {p.name for p in (claude / "skills").glob("*") if p.is_dir()}
    names |= {p.stem for p in (claude / "agents").glob("*.md")}
    names |= {p.stem for p in (claude / "commands").glob("*.md")}
    names.discard(OWN_PLUGIN)
    return markers + sorted(f"{n}:" if n in BUILTIN_NAMES else n for n in names)


def find_hits(inventory: str, forbid: list[str]) -> list[str]:
    """Case-insensitive match that will not hit inside a longer name (sip vs gossip)."""
    low = inventory.lower()
    hits = []
    for marker in forbid:
        pattern = re.escape(marker.lower())
        if marker[:1].isalnum():
            pattern = r"(?<![\w-])" + pattern
        if marker[-1:].isalnum():
            pattern += r"(?![\w-])"
        if re.search(pattern, low):
            hits.append(marker)
    return hits


def doctor(config: Config, repo_root: Path, forbid: list[str]) -> tuple[list[str], str]:
    with tempfile.TemporaryDirectory(prefix="aci-doctor-") as tmp:
        task = Task(id="doctor", axis="make", split="dev", prompt=DOCTOR_PROMPT,
                    output="inventory.txt", dir=Path(tmp))
        out = Path(tmp) / "out"
        run_sample(task, config, 0, out, repo_root)
        path = sample_dir(out, "doctor", config.name, 0) / "output" / "inventory.txt"
        inventory = path.read_text() if path.exists() else ""
    return find_hits(inventory, forbid), inventory
```

`bench/aci/cli.py`:
```python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .adapter import load_config
from .doctor import default_forbid, doctor
from .judge import judge_run
from .runner import run_all
from .score import render_markdown, summarize
from .tasks import SPLITS, TASKS_ROOT, load_tasks

REPO_ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aci", description="Agent Creativity Index")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run agents on tasks")
    run.add_argument("--config", action="append", required=True, help="agent config yaml; repeat for A and B")
    run.add_argument("--split", choices=SPLITS)
    run.add_argument("--only", help="comma-separated task ids")
    run.add_argument("-k", type=int, default=3, help="samples per task and config")
    run.add_argument("-j", type=int, default=1, help="parallel jobs")
    run.add_argument("--out", required=True)
    run.add_argument("--tasks-dir", default=str(TASKS_ROOT))

    judge = sub.add_parser("judge", help="blind pairwise judging of a run")
    judge.add_argument("run_dir")
    judge.add_argument("--a", required=True, help="baseline config name")
    judge.add_argument("--b", required=True, help="treatment config name")
    judge.add_argument("--judge", required=True, help="judge config yaml")
    judge.add_argument("-j", type=int, default=1)
    judge.add_argument("--tasks-dir", default=str(TASKS_ROOT))

    score = sub.add_parser("score", help="compute the index")
    score.add_argument("run_dir")
    score.add_argument("--split", choices=SPLITS, default="holdout")
    score.add_argument("--tasks-dir", default=str(TASKS_ROOT))

    doc = sub.add_parser("doctor", help="check that an agent config runs without the user's global setup")
    doc.add_argument("config")
    doc.add_argument("--forbid", action="append", default=[], help="extra marker that must not appear")

    args = parser.parse_args(argv)

    if args.command == "run":
        tasks = load_tasks(Path(args.tasks_dir), args.split)
        if args.only:
            wanted = set(args.only.split(","))
            tasks = [t for t in tasks if t.id in wanted]
        configs = [load_config(Path(c)) for c in args.config]
        run_all(tasks, configs, args.k, Path(args.out), REPO_ROOT, args.j)
        return 0
    if args.command == "judge":
        judge_run(Path(args.run_dir), load_tasks(Path(args.tasks_dir)), args.a, args.b,
                  load_config(Path(args.judge)), args.j)
        return 0
    if args.command == "score":
        run_dir = Path(args.run_dir)
        summary = summarize(run_dir, load_tasks(Path(args.tasks_dir), args.split))
        (run_dir / "report.json").write_text(json.dumps({"split": args.split, **summary}, indent=2))
        markdown = render_markdown(summary, args.split)
        (run_dir / "report.md").write_text(markdown)
        print(markdown)
        return 0
    hits, inventory = doctor(load_config(Path(args.config)), REPO_ROOT, default_forbid() + args.forbid)
    print(inventory or "(no inventory.txt produced)")
    if not inventory:
        print("FAIL: the agent produced no inventory", file=sys.stderr)
        return 2
    if hits:
        print(f"FAIL: global items leaked into the session: {', '.join(hits)}", file=sys.stderr)
        return 1
    print("PASS: no global items detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: 통과 확인**

Run: `cd bench && uv run pytest -v`
Expected: 전체 통과(30 passed)

- [ ] **Step 6: 커밋**

```bash
git add bench/aci/doctor.py bench/aci/cli.py bench/configs bench/tests/test_doctor.py bench/tests/test_cli.py
git commit -m "feat: aci CLI, isolation doctor, zero-cost smoke test"
```

---

### Task 6: solve 축 태스크 8개

모든 solve 태스크는 같은 모양이다: `task.yaml`, `starter/solution.py`(NotImplementedError), `tests/test_solution.py`(AST 제약 검사 + 동작 검사), `reference.py`(제약을 지키는 정답, 에이전트에게 복사되지 않음), `obvious.py`(동작은 맞지만 제약을 어기는 뻔한 풀이 — 테스트가 이것을 반드시 떨어뜨려야 함).

모든 `tests/test_solution.py`는 이 머리말로 시작한다(아래 각 태스크에 전체 포함):
```python
import ast
from pathlib import Path

import solution

TREE = ast.parse((Path(__file__).resolve().parent.parent / "solution.py").read_text())
NODES = list(ast.walk(TREE))
NAMES = {n.id for n in NODES if isinstance(n, ast.Name)}
ATTRS = {n.attr for n in NODES if isinstance(n, ast.Attribute)}


def has(*types):
    return any(isinstance(n, types) for n in NODES)
```

**Files:**
- Create: `bench/tasks/solve/<id>/{task.yaml, starter/solution.py, tests/test_solution.py, reference.py, obvious.py}` × 8
- Create: `bench/tests/test_solve_tasks.py`

**Interfaces:**
- Consumes: `load_tasks`(Task 1), `run_check`(Task 2)

- [ ] **Step 1: 태스크 검증 테스트 작성**

`bench/tests/test_solve_tasks.py`:
```python
import shutil

import pytest

from aci.runner import run_check
from aci.tasks import load_tasks

SOLVE = [t for t in load_tasks() if t.axis == "solve"]


def prepared(task, tmp_path, source):
    work = tmp_path / source
    shutil.copytree(task.dir / "starter", work)
    if source != "starter":
        shutil.copy(task.dir / f"{source}.py", work / "solution.py")
    return work


def test_eight_solve_tasks():
    assert len(SOLVE) == 8


@pytest.mark.parametrize("task", SOLVE, ids=lambda t: t.id)
def test_reference_passes_while_starter_and_obvious_fail(task, tmp_path):
    assert run_check(task, prepared(task, tmp_path, "reference"))
    assert not run_check(task, prepared(task, tmp_path, "starter"))
    assert not run_check(task, prepared(task, tmp_path, "obvious"))
```

- [ ] **Step 2: 실패 확인**

Run: `cd bench && uv run pytest tests/test_solve_tasks.py -v`
Expected: FAIL — `assert 0 == 8`

- [ ] **Step 3: dev 태스크 4개 작성**

`bench/tasks/solve/solve-sort-no-compare/task.yaml`:
```yaml
id: solve-sort-no-compare
axis: solve
split: dev
output: solution.py
check: "{python} -m pytest -q tests"
prompt: |
  Implement `sort_numbers(nums)` in solution.py. It takes a list of up to 10,000 integers,
  each between 0 and 1000 inclusive, and returns them in ascending order.

  Rules (checked automatically by parsing your code):
  - no comparison operators at all (<, >, <=, >=, ==, !=, in, not in, is, is not)
  - no sorted(), .sort(), min(), or max()
  - no import statements

  Hidden tests check correctness. Edit only solution.py.
```
`starter/solution.py`:
```python
def sort_numbers(nums: list[int]) -> list[int]:
    raise NotImplementedError
```
`tests/test_solution.py`:
```python
import ast
import random
from pathlib import Path

import solution

TREE = ast.parse((Path(__file__).resolve().parent.parent / "solution.py").read_text())
NODES = list(ast.walk(TREE))
NAMES = {n.id for n in NODES if isinstance(n, ast.Name)}
ATTRS = {n.attr for n in NODES if isinstance(n, ast.Attribute)}


def has(*types):
    return any(isinstance(n, types) for n in NODES)


def test_constraints():
    assert not has(ast.Compare, ast.Import, ast.ImportFrom)
    assert not NAMES & {"sorted", "min", "max"}
    assert "sort" not in ATTRS


def test_sorts_random_lists():
    rng = random.Random(7)
    for size in (0, 1, 2, 50, 10_000):
        nums = [rng.randint(0, 1000) for _ in range(size)]
        assert solution.sort_numbers(list(nums)) == sorted(nums)


def test_duplicates_and_bounds():
    assert solution.sort_numbers([1000, 0, 1000, 0, 5]) == [0, 0, 5, 1000, 1000]
```
`reference.py`:
```python
def sort_numbers(nums):
    counts = [0] * 1001
    for n in nums:
        counts[n] += 1
    out = []
    for value, count in enumerate(counts):
        out.extend([value] * count)
    return out
```
`obvious.py`:
```python
def sort_numbers(nums):
    return sorted(nums)
```

`bench/tasks/solve/solve-fizzbuzz-no-branch/task.yaml`:
```yaml
id: solve-fizzbuzz-no-branch
axis: solve
split: dev
output: solution.py
check: "{python} -m pytest -q tests"
prompt: |
  Implement `fizzbuzz(n)` in solution.py. It returns a list of strings for the numbers 1 to n:
  "Fizz" for multiples of 3, "Buzz" for multiples of 5, "FizzBuzz" for multiples of both,
  and the number itself otherwise. fizzbuzz(0) returns an empty list.

  Rules (checked automatically by parsing your code):
  - no if/elif/else statements, no conditional expressions (x if c else y), no match
  - no `and` / `or`, no comparison operators (<, >, ==, !=, in, is, ...)
  - no `if` clauses inside comprehensions
  - no import statements

  Hidden tests check correctness. Edit only solution.py.
```
`starter/solution.py`:
```python
def fizzbuzz(n: int) -> list[str]:
    raise NotImplementedError
```
`tests/test_solution.py`:
```python
import ast
from pathlib import Path

import solution

TREE = ast.parse((Path(__file__).resolve().parent.parent / "solution.py").read_text())
NODES = list(ast.walk(TREE))
NAMES = {n.id for n in NODES if isinstance(n, ast.Name)}
ATTRS = {n.attr for n in NODES if isinstance(n, ast.Attribute)}


def has(*types):
    return any(isinstance(n, types) for n in NODES)


def expected(n):
    out = []
    for i in range(1, n + 1):
        out.append("FizzBuzz" if i % 15 == 0 else "Fizz" if i % 3 == 0 else "Buzz" if i % 5 == 0 else str(i))
    return out


def test_constraints():
    assert not has(ast.If, ast.IfExp, ast.Match, ast.BoolOp, ast.Compare, ast.Import, ast.ImportFrom)
    assert not any(isinstance(n, ast.comprehension) and n.ifs for n in NODES)


def test_values():
    assert solution.fizzbuzz(15)[-1] == "FizzBuzz"
    for n in (0, 1, 15, 100):
        assert solution.fizzbuzz(n) == expected(n)
```
`reference.py`:
```python
def fizzbuzz(n):
    out = []
    for i in range(1, n + 1):
        word = "Fizz" * (not i % 3) + "Buzz" * (not i % 5)
        out.append((word, str(i))[not word])
    return out
```
`obvious.py`:
```python
def fizzbuzz(n):
    out = []
    for i in range(1, n + 1):
        if i % 15 == 0:
            out.append("FizzBuzz")
        elif i % 3 == 0:
            out.append("Fizz")
        elif i % 5 == 0:
            out.append("Buzz")
        else:
            out.append(str(i))
    return out
```

`bench/tasks/solve/solve-max-no-compare/task.yaml`:
```yaml
id: solve-max-no-compare
axis: solve
split: dev
output: solution.py
check: "{python} -m pytest -q tests"
prompt: |
  Implement `largest(values)` in solution.py. It takes a non-empty list of integers between
  -1,000,000,000 and 1,000,000,000 and returns the largest one.

  Rules (checked automatically by parsing your code):
  - no comparison operators (<, >, ==, !=, in, is, ...)
  - no if statements, conditional expressions, `and` / `or`
  - no max(), min(), sorted(), .sort()
  - no import statements

  Hidden tests check correctness. Edit only solution.py.
```
`starter/solution.py`:
```python
def largest(values: list[int]) -> int:
    raise NotImplementedError
```
`tests/test_solution.py`:
```python
import ast
import random
from pathlib import Path

import solution

TREE = ast.parse((Path(__file__).resolve().parent.parent / "solution.py").read_text())
NODES = list(ast.walk(TREE))
NAMES = {n.id for n in NODES if isinstance(n, ast.Name)}
ATTRS = {n.attr for n in NODES if isinstance(n, ast.Attribute)}


def has(*types):
    return any(isinstance(n, types) for n in NODES)


def test_constraints():
    assert not has(ast.Compare, ast.If, ast.IfExp, ast.BoolOp, ast.Import, ast.ImportFrom)
    assert not NAMES & {"max", "min", "sorted"}
    assert "sort" not in ATTRS


def test_values():
    rng = random.Random(3)
    assert solution.largest([5]) == 5
    assert solution.largest([-3, -1, -2]) == -1
    for _ in range(200):
        vals = [rng.randint(-10**9, 10**9) for _ in range(rng.randint(1, 50))]
        assert solution.largest(vals) == max(vals)
```
`reference.py`:
```python
def largest(values):
    best = values[0]
    for v in values[1:]:
        best = (best + v + abs(best - v)) // 2
    return best
```
`obvious.py`:
```python
def largest(values):
    return max(values)
```

`bench/tasks/solve/solve-reverse-words-no-split/task.yaml`:
```yaml
id: solve-reverse-words-no-split
axis: solve
split: dev
output: solution.py
check: "{python} -m pytest -q tests"
prompt: |
  Implement `reverse_words(text)` in solution.py. A word is a maximal run of non-space
  characters; only the space character separates words. Return the words in reverse order
  joined by single spaces, with no leading or trailing spaces. An empty or all-space input
  returns "".

  Rules (checked automatically by parsing your code):
  - no .split(), .rsplit(), .partition(), .rpartition(), .reverse()
  - no reversed(), no slices with a step (such as [::-1])
  - no import statements

  Hidden tests check correctness. Edit only solution.py.
```
`starter/solution.py`:
```python
def reverse_words(text: str) -> str:
    raise NotImplementedError
```
`tests/test_solution.py`:
```python
import ast
from pathlib import Path

import solution

TREE = ast.parse((Path(__file__).resolve().parent.parent / "solution.py").read_text())
NODES = list(ast.walk(TREE))
NAMES = {n.id for n in NODES if isinstance(n, ast.Name)}
ATTRS = {n.attr for n in NODES if isinstance(n, ast.Attribute)}


def has(*types):
    return any(isinstance(n, types) for n in NODES)


def test_constraints():
    assert not has(ast.Import, ast.ImportFrom)
    assert not ATTRS & {"split", "rsplit", "partition", "rpartition", "reverse"}
    assert "reversed" not in NAMES
    assert not any(isinstance(n, ast.Slice) and n.step is not None for n in NODES)


def test_values():
    assert solution.reverse_words("the quick brown fox") == "fox brown quick the"
    assert solution.reverse_words("  hello   world  ") == "world hello"
    assert solution.reverse_words("single") == "single"
    assert solution.reverse_words("") == ""
    assert solution.reverse_words("   ") == ""
```
`reference.py`:
```python
def reverse_words(text):
    words = []
    current = ""
    for ch in text + " ":
        if ch == " ":
            if current:
                words.insert(0, current)
            current = ""
        else:
            current += ch
    return " ".join(words)
```
`obvious.py`:
```python
def reverse_words(text):
    return " ".join(reversed(text.split()))
```

- [ ] **Step 4: holdout 태스크 4개 작성**

`bench/tasks/solve/solve-palindrome-no-loops/task.yaml`:
```yaml
id: solve-palindrome-no-loops
axis: solve
split: holdout
output: solution.py
check: "{python} -m pytest -q tests"
prompt: |
  Implement `is_palindrome(text)` in solution.py. Ignore case and every character that is
  not a letter or digit; return True if what remains reads the same both ways. Inputs are at
  most 500 characters. The empty string is a palindrome.

  Rules (checked automatically by parsing your code):
  - no for or while loops, and no comprehensions or generator expressions
  - no reversed(), no .reverse(), no slices with a step (such as [::-1])
  - no import statements

  Hidden tests check correctness. Edit only solution.py.
```
`starter/solution.py`:
```python
def is_palindrome(text: str) -> bool:
    raise NotImplementedError
```
`tests/test_solution.py`:
```python
import ast
from pathlib import Path

import solution

TREE = ast.parse((Path(__file__).resolve().parent.parent / "solution.py").read_text())
NODES = list(ast.walk(TREE))
NAMES = {n.id for n in NODES if isinstance(n, ast.Name)}
ATTRS = {n.attr for n in NODES if isinstance(n, ast.Attribute)}


def has(*types):
    return any(isinstance(n, types) for n in NODES)


def test_constraints():
    assert not has(ast.For, ast.While, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp,
                   ast.Import, ast.ImportFrom)
    assert "reversed" not in NAMES and "reverse" not in ATTRS
    assert not any(isinstance(n, ast.Slice) and n.step is not None for n in NODES)


def test_values():
    assert solution.is_palindrome("A man, a plan, a canal: Panama")
    assert solution.is_palindrome("")
    assert solution.is_palindrome("No 'x' in Nixon")
    assert not solution.is_palindrome("palindrome")
    assert solution.is_palindrome("ab" * 100 + "ba" * 100)
    assert not solution.is_palindrome("ab" * 200)
```
`reference.py`:
```python
def is_palindrome(text):
    chars = "".join(filter(str.isalnum, text)).lower()
    return _mirror(chars, 0, len(chars) - 1)


def _mirror(s, i, j):
    if i >= j:
        return True
    return s[i] == s[j] and _mirror(s, i + 1, j - 1)
```
`obvious.py`:
```python
def is_palindrome(text):
    s = "".join(c for c in text.lower() if c.isalnum())
    return s == s[::-1]
```

`bench/tasks/solve/solve-add-no-arithmetic/task.yaml`:
```yaml
id: solve-add-no-arithmetic
axis: solve
split: holdout
output: solution.py
check: "{python} -m pytest -q tests"
prompt: |
  Implement `add(a, b)` in solution.py for integers 0 <= a, b <= 1,000,000. Return a + b.

  Rules (checked automatically by parsing your code):
  - no arithmetic operators: +, -, *, /, //, %, ** (including +=, -= and unary minus)
  - no sum(), and no attribute whose name contains "add" or "sub" (such as __add__)
  - no import statements

  Hidden tests check correctness. Edit only solution.py.
```
`starter/solution.py`:
```python
def add(a: int, b: int) -> int:
    raise NotImplementedError
```
`tests/test_solution.py`:
```python
import ast
import random
from pathlib import Path

import solution

TREE = ast.parse((Path(__file__).resolve().parent.parent / "solution.py").read_text())
NODES = list(ast.walk(TREE))
NAMES = {n.id for n in NODES if isinstance(n, ast.Name)}
ATTRS = {n.attr for n in NODES if isinstance(n, ast.Attribute)}
ARITH = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.MatMult)


def has(*types):
    return any(isinstance(n, types) for n in NODES)


def test_constraints():
    assert not any(isinstance(n, (ast.BinOp, ast.AugAssign)) and isinstance(n.op, ARITH) for n in NODES)
    assert not any(isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub) for n in NODES)
    assert not has(ast.Import, ast.ImportFrom)
    assert "sum" not in NAMES
    assert not any("add" in a or "sub" in a for a in ATTRS)


def test_values():
    rng = random.Random(11)
    assert solution.add(0, 0) == 0
    assert solution.add(10**6, 10**6) == 2 * 10**6
    for _ in range(500):
        a, b = rng.randint(0, 10**6), rng.randint(0, 10**6)
        assert solution.add(a, b) == a + b
```
`reference.py`:
```python
def add(a, b):
    while b:
        carry = (a & b) << 1
        a = a ^ b
        b = carry
    return a
```
`obvious.py`:
```python
def add(a, b):
    return a + b
```

`bench/tasks/solve/solve-count-vowels-no-loops/task.yaml`:
```yaml
id: solve-count-vowels-no-loops
axis: solve
split: holdout
output: solution.py
check: "{python} -m pytest -q tests"
prompt: |
  Implement `count_vowels(text)` in solution.py. Return how many characters of text are
  vowels (a, e, i, o, u), ignoring case. "y" is not a vowel.

  Rules (checked automatically by parsing your code):
  - no for or while loops, and no comprehensions or generator expressions
  - no .count() and no sum()
  - no import statements

  Hidden tests check correctness. Edit only solution.py.
```
`starter/solution.py`:
```python
def count_vowels(text: str) -> int:
    raise NotImplementedError
```
`tests/test_solution.py`:
```python
import ast
from pathlib import Path

import solution

TREE = ast.parse((Path(__file__).resolve().parent.parent / "solution.py").read_text())
NODES = list(ast.walk(TREE))
NAMES = {n.id for n in NODES if isinstance(n, ast.Name)}
ATTRS = {n.attr for n in NODES if isinstance(n, ast.Attribute)}


def has(*types):
    return any(isinstance(n, types) for n in NODES)


def test_constraints():
    assert not has(ast.For, ast.While, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp,
                   ast.Import, ast.ImportFrom)
    assert "count" not in ATTRS and "sum" not in NAMES


def test_values():
    assert solution.count_vowels("") == 0
    assert solution.count_vowels("rhythm") == 0
    assert solution.count_vowels("AEIOU aeiou") == 10
    assert solution.count_vowels("Hello, World!") == 3
    assert solution.count_vowels("The quick brown fox jumps over the lazy dog. " * 50) == 11 * 50
```
`reference.py`:
```python
def count_vowels(text):
    return len(list(filter(lambda c: c in "aeiou", text.lower())))
```
`obvious.py`:
```python
def count_vowels(text):
    return sum(text.lower().count(v) for v in "aeiou")
```

`bench/tasks/solve/solve-transpose-no-index/task.yaml`:
```yaml
id: solve-transpose-no-index
axis: solve
split: holdout
output: solution.py
check: "{python} -m pytest -q tests"
prompt: |
  Implement `transpose(matrix)` in solution.py. matrix is a rectangular list of lists of
  integers (possibly empty). Return its transpose as a list of lists; transpose([]) is [].

  Rules (checked automatically by parsing your code):
  - no subscripting of any kind (no x[i], x[i:j], and no subscripted type hints)
  - no zip()
  - no import statements

  Hidden tests check correctness. Edit only solution.py.
```
`starter/solution.py`:
```python
def transpose(matrix):
    """Return the transpose of a rectangular list of lists."""
    raise NotImplementedError
```
`tests/test_solution.py`:
```python
import ast
from pathlib import Path

import solution

TREE = ast.parse((Path(__file__).resolve().parent.parent / "solution.py").read_text())
NODES = list(ast.walk(TREE))
NAMES = {n.id for n in NODES if isinstance(n, ast.Name)}
ATTRS = {n.attr for n in NODES if isinstance(n, ast.Attribute)}


def has(*types):
    return any(isinstance(n, types) for n in NODES)


def test_constraints():
    assert not has(ast.Subscript, ast.Import, ast.ImportFrom)
    assert "zip" not in NAMES


def test_values():
    assert solution.transpose([]) == []
    assert solution.transpose([[7]]) == [[7]]
    assert solution.transpose([[1, 2, 3], [4, 5, 6]]) == [[1, 4], [2, 5], [3, 6]]
    m = [[r * 10 + c for c in range(7)] for r in range(5)]
    assert solution.transpose(m) == [list(col) for col in zip(*m)]
```
`reference.py`:
```python
def transpose(matrix):
    if not matrix:
        return []
    width = len(next(iter(matrix)))
    rows = list(map(iter, matrix))
    return [list(map(next, rows)) for _ in range(width)]
```
`obvious.py`:
```python
def transpose(matrix):
    return [list(col) for col in zip(*matrix)]
```

- [ ] **Step 5: 통과 확인**

Run: `cd bench && uv run pytest tests/test_solve_tasks.py -v`
Expected: 9 passed. 어떤 태스크든 실패하면 그 태스크의 테스트나 reference를 고친다. 제약을 느슨하게 만들어 obvious가 통과하게 두지 않는다.

- [ ] **Step 6: 커밋**

```bash
git add bench/tasks/solve bench/tests/test_solve_tasks.py
git commit -m "feat: eight constraint-driven solve tasks with reference and obvious solutions"
```

---

### Task 7: diverge·make 축 태스크 16개

**Files:**
- Create: `bench/tasks/diverge/<id>/task.yaml` × 8, `bench/tasks/make/<id>/task.yaml` × 8
- Create: `bench/tests/test_task_set.py`

**Interfaces:**
- Consumes: `load_tasks`(Task 1)

- [ ] **Step 1: 실패하는 테스트 작성**

`bench/tests/test_task_set.py`:
```python
from collections import Counter

from aci.tasks import AXES, SPLITS, load_tasks


def test_shipped_task_set_shape():
    tasks = load_tasks()
    assert len(tasks) == 24
    assert Counter((t.axis, t.split) for t in tasks) == {(a, s): 4 for a in AXES for s in SPLITS}
```

- [ ] **Step 2: 실패 확인**

Run: `cd bench && uv run pytest tests/test_task_set.py -v`
Expected: FAIL — `assert 8 == 24`

- [ ] **Step 3: diverge 태스크 8개 작성**

모든 diverge 프롬프트는 같은 마지막 문단으로 끝난다: `Write them to ideas.md as a numbered list of exactly 10 items, one or two sentences each. Write nothing else in that file.`

`bench/tasks/diverge/diverge-git-uses/task.yaml`:
```yaml
id: diverge-git-uses
axis: diverge
split: dev
output: ideas.md
prompt: |
  List 10 uses for a git repository other than tracking the history of source code.

  Write them to ideas.md as a numbered list of exactly 10 items, one or two sentences each.
  Write nothing else in that file.
```
`bench/tasks/diverge/diverge-flaky-ci/task.yaml`:
```yaml
id: diverge-flaky-ci
axis: diverge
split: dev
output: ideas.md
prompt: |
  A test passes on every developer's laptop but fails in CI, and only on Tuesdays.
  List 10 distinct hypotheses for the cause.

  Write them to ideas.md as a numbered list of exactly 10 items, one or two sentences each.
  Write nothing else in that file.
```
`bench/tasks/diverge/diverge-onboarding/task.yaml`:
```yaml
id: diverge-onboarding
axis: diverge
split: dev
output: ideas.md
prompt: |
  List 10 ways to help a new engineer learn a large, unfamiliar codebase in their first
  week without writing any documentation.

  Write them to ideas.md as a numbered list of exactly 10 items, one or two sentences each.
  Write nothing else in that file.
```
`bench/tasks/diverge/diverge-mic-calendar/task.yaml`:
```yaml
id: diverge-mic-calendar
axis: diverge
split: dev
output: ideas.md
prompt: |
  List 10 product ideas that use only two things: a microphone and a calendar API.

  Write them to ideas.md as a numbered list of exactly 10 items, one or two sentences each.
  Write nothing else in that file.
```
`bench/tasks/diverge/diverge-wrong-answer/task.yaml`:
```yaml
id: diverge-wrong-answer
axis: diverge
split: holdout
output: ideas.md
prompt: |
  List 10 ways to tell that an answer written by an AI model is probably wrong, without
  knowing the correct answer.

  Write them to ideas.md as a numbered list of exactly 10 items, one or two sentences each.
  Write nothing else in that file.
```
`bench/tasks/diverge/diverge-one-pixel/task.yaml`:
```yaml
id: diverge-one-pixel
axis: diverge
split: holdout
output: ideas.md
prompt: |
  List 10 uses for a 1x1 pixel image in software.

  Write them to ideas.md as a numbered list of exactly 10 items, one or two sentences each.
  Write nothing else in that file.
```
`bench/tasks/diverge/diverge-bike-share/task.yaml`:
```yaml
id: diverge-bike-share
axis: diverge
split: holdout
output: ideas.md
prompt: |
  A city added 30% more shared bikes, and total rides went down. List 10 distinct
  hypotheses for why.

  Write them to ideas.md as a numbered list of exactly 10 items, one or two sentences each.
  Write nothing else in that file.
```
`bench/tasks/diverge/diverge-writer-unstuck/task.yaml`:
```yaml
id: diverge-writer-unstuck
axis: diverge
split: holdout
output: ideas.md
prompt: |
  List 10 features a text editor could have to help a stuck writer, none of which
  generate text with AI.

  Write them to ideas.md as a numbered list of exactly 10 items, one or two sentences each.
  Write nothing else in that file.
```

- [ ] **Step 4: make 태스크 8개 작성**

`bench/tasks/make/make-error-narrator/task.yaml`:
```yaml
id: make-error-narrator
axis: make
split: dev
output: story.md
prompt: |
  Write a short story narrated by a compiler error message. Save it as story.md.

  Requirements:
  - 250 to 350 words
  - the narrator is the error message itself
  - the story has an ending
```
`bench/tasks/make/make-one-key-game/task.yaml`:
```yaml
id: make-one-key-game
axis: make
split: dev
output: game.html
prompt: |
  Make a browser game played with only the space bar. Save it as game.html.

  Requirements:
  - one self-contained HTML file with no external resources (no CDNs, remote images, or fonts)
  - the game has a goal and a way to win or lose
  - instructions appear on screen
```
`bench/tasks/make/make-git-log-poem/task.yaml`:
```yaml
id: make-git-log-poem
axis: make
split: dev
output: poem.txt
prompt: |
  Write a poem in the form of `git log --oneline` output. Save it as poem.txt.

  Requirements:
  - exactly 12 lines
  - each line is a 7-character lowercase hexadecimal hash, one space, then a commit message
  - read from top to bottom, the lines tell a story
```
`bench/tasks/make/make-library-404/task.yaml`:
```yaml
id: make-library-404
axis: make
split: dev
output: 404.html
prompt: |
  Design the 404 "page not found" page for a public library's website. Save it as 404.html.

  Requirements:
  - one self-contained HTML file with no external resources
  - it includes a link back to the home page (href="/")
  - it is readable on a 360px-wide phone screen
```
`bench/tasks/make/make-last-backup/task.yaml`:
```yaml
id: make-last-backup
axis: make
split: holdout
output: story.md
prompt: |
  Write a short story about the last working backup on Earth. Save it as story.md.

  Requirements:
  - 250 to 350 words
  - the story has an ending
```
`bench/tasks/make/make-typing-game/task.yaml`:
```yaml
id: make-typing-game
axis: make
split: holdout
output: game.html
prompt: |
  Make a browser game in which the player must type to play. Save it as game.html.

  Requirements:
  - one self-contained HTML file with no external resources (no CDNs, remote images, or fonts)
  - the game has a goal and a way to win or lose
  - instructions appear on screen
```
`bench/tasks/make/make-recipe-program/task.yaml`:
```yaml
id: make-recipe-program
axis: make
split: holdout
output: recipe.md
prompt: |
  Write a recipe that is also a program: a real dish whose instructions are written as
  pseudocode with functions, loops, or conditionals. Save it as recipe.md.

  Requirements:
  - a person could actually cook the dish by following it
  - the ingredients are listed with quantities
```
`bench/tasks/make/make-repair-landing/task.yaml`:
```yaml
id: make-repair-landing
axis: make
split: holdout
output: index.html
prompt: |
  Design a landing page for a shop that repairs time machines. Save it as index.html.

  Requirements:
  - one self-contained HTML file with no external resources
  - a headline, a list of services, and a way to contact the shop
  - it is readable on a 360px-wide phone screen
```

- [ ] **Step 5: 통과 확인**

Run: `cd bench && uv run pytest -v`
Expected: 전체 통과(40 passed)

- [ ] **Step 6: 커밋**

```bash
git add bench/tasks/diverge bench/tasks/make bench/tests/test_task_set.py
git commit -m "feat: diverge and make task sets"
```

---

### Task 8: 실제 에이전트·심판 설정과 격리 검증

이 태스크는 실측이다. 후보를 순서대로 시도하고 `aci doctor`가 통과하는 첫 후보를 채택한다. 결과는 `docs/isolation.md`에 기록한다.

**Files:**
- Create: `bench/configs/claude-base.yaml`, `bench/configs/claude-base-copy.yaml`, `bench/configs/claude-skill.yaml`, `bench/configs/judge-codex.yaml`, `docs/isolation.md`

**Interfaces:**
- Consumes: `aci doctor`(Task 5), `call_judge`, `load_config`(Task 2·3)
- Produces: 설정 이름 `claude-base`, `claude-base-copy`, `claude-skill`, `codex` — Task 9가 이 이름을 쓴다.

- [ ] **Step 1: 후보 1(구독 로그인, 전역 설정 소스 배제)로 기준 설정 작성**

`bench/configs/claude-base.yaml`:
```yaml
# Baseline: Claude Code headless with none of the user's global settings, plugins, or MCP servers.
name: claude-base
cmd: >-
  claude -p --setting-sources project --strict-mcp-config
  --dangerously-skip-permissions < {prompt_file}
timeout: 900
```

- [ ] **Step 2: doctor 실행**

Run: `cd bench && uv run aci doctor configs/claude-base.yaml`
Expected: `PASS: no global items detected`. 출력된 inventory 전체를 `docs/isolation.md`에 붙인다.

FAIL이면(대개 `~/.claude/CLAUDE.md`가 보이는 경우) 다음 후보로 간다.
- 후보 2: Step 1의 설정에 `env:`로 `CLAUDE_CONFIG_DIR: "{repo_root}/bench/.claude-isolated"`를 더한다. 인증 오류(로그인 요구)가 나면 사용자가 직접 로그인해야 한다. 이때 멈추고 사용자에게 다음 명령을 실행해 `/login` 하도록 요청한다(사용자에게 알림):
  ```bash
  CLAUDE_CONFIG_DIR=<repo>/bench/.claude-isolated claude
  ```
- 후보 3(`ANTHROPIC_API_KEY`가 있을 때만): `cmd: claude -p --bare --dangerously-skip-permissions < {prompt_file}`.
- 세 후보 모두 실패하면 멈추고 사용자에게 보고한다. 실패한 설정으로 진행하지 않는다.

- [ ] **Step 3: 나머지 에이전트 설정 작성**

채택한 후보의 `cmd`/`env`를 그대로 복사한다. (아래는 후보 1을 채택한 경우.)

`bench/configs/claude-base-copy.yaml`:
```yaml
# Identical to claude-base, under another name, for the A/A sanity check.
name: claude-base-copy
cmd: >-
  claude -p --setting-sources project --strict-mcp-config
  --dangerously-skip-permissions < {prompt_file}
timeout: 900
```

`bench/configs/claude-skill.yaml`:
```yaml
# Treatment: the baseline plus this repository loaded as a plugin.
name: claude-skill
cmd: >-
  claude -p --setting-sources project --strict-mcp-config
  --plugin-dir {repo_root} --dangerously-skip-permissions < {prompt_file}
timeout: 900
```

Run: `cd bench && uv run aci doctor configs/claude-skill.yaml`
Expected: `PASS` (이 저장소 플러그인 이름은 금지 목록에서 빠져 있다)

참고: 금지 목록은 설치 플러그인뿐 아니라 `~/.claude/skills`, `~/.claude/agents`, `~/.claude/commands`의 사용자 항목도 포함한다. 후보 1이 이것들을 못 막으면 후보 2(별도 설정 폴더)로 간다.

- [ ] **Step 4: 심판 설정 작성과 확인**

`bench/configs/judge-codex.yaml`:
```yaml
# Judge from a different model family than the Claude agents under test.
name: codex
cmd: >-
  codex exec --skip-git-repo-check --ephemeral -s read-only
  -o {verdict_file} - < {judge_prompt_file}
timeout: 300
```

Run:
```bash
cd bench && uv run python -c "from pathlib import Path; from aci.adapter import load_config; from aci.judge import call_judge; print(call_judge(load_config(Path('configs/judge-codex.yaml')), 'Reply with only this JSON object: {\"winner\": 1, \"reason\": \"test\"}'))"
```
Expected: `('1', ...)`. `None`이 나오면 `-o` 파일과 stdout을 확인하고 cmd를 고친다.

- [ ] **Step 5: 기록과 커밋**

`docs/isolation.md`에 적는다: 시도한 후보와 각 doctor 결과(PASS/FAIL, 걸린 항목), 채택한 후보, 남는 한계("doctor는 에이전트의 자기 보고에 의존하므로 보이지 않게 주입된 항목은 못 잡는다", "codex 심판은 사용자의 codex 전역 설정을 읽을 수 있다").

```bash
git add bench/configs docs/isolation.md
git commit -m "feat: isolated Claude Code configs and codex judge"
```

---

### Task 9: A/A 검사(성공 기준 2)

같은 설정을 A와 B에 넣어 채점기 잡음을 잰다. 비용이 드는 실제 실행이므로 백그라운드로 돌린다. dev split, k=1(에이전트 실행 24회, 심판 호출 최대 48회).

**Files:**
- Create: `docs/results/2026-10-12-aa-dev.md`

**Interfaces:**
- Consumes: `aci run/judge/score`(Task 5), 설정 `claude-base`, `claude-base-copy`, `codex`(Task 8)

- [ ] **Step 1: 실행**

```bash
cd bench && uv run aci run --config configs/claude-base.yaml --config configs/claude-base-copy.yaml --split dev -k 1 -j 3 --out runs/aa-dev
```
Expected: 24줄의 진행 로그. 끝난 뒤 `runs/aa-dev/*/claude-base*/0/meta.json` 24개.

- [ ] **Step 2: 판정**

```bash
cd bench && uv run aci judge runs/aa-dev --a claude-base --b claude-base-copy --judge configs/judge-codex.yaml -j 3
```
Expected: 12줄의 판정 로그.

- [ ] **Step 3: 점수**

```bash
cd bench && uv run aci score runs/aa-dev --split dev
```
Expected: 지수의 95% 신뢰구간이 50을 포함한다. 실패·시간초과 0에 가깝다.

포함하지 않으면 멈추고 보고한다. 결과를 맞추려고 판정 규칙이나 프롬프트를 고치지 않는다. 원인 후보(심판의 위치 편향, 표본 부족, 한쪽 실행 실패)를 `report.md`의 수치로 적는다.

- [ ] **Step 4: 기록과 커밋**

`runs/aa-dev/report.md`를 `docs/results/2026-10-12-aa-dev.md`로 복사하고, 맨 위에 실행 조건(모델·CLI 버전 `claude --version`, `codex --version`, k, split, 날짜)과 한 줄 결론을 적는다.

```bash
git add docs/results
git commit -m "docs: A/A sanity check on dev split"
```

---

### Task 10: README와 라이선스

**Files:**
- Create: `README.md`, `LICENSE`

- [ ] **Step 1: 라이선스 복사**

```bash
cp ~/.claude/plugins/cache/itsinseong/value-for-fable/1.0.1/LICENSE LICENSE
head -2 LICENSE
```
Expected: `GNU AFFERO GENERAL PUBLIC LICENSE`

- [ ] **Step 2: README 작성**

`README.md`:
````markdown
# Agent Creativity Index (ACI)

ACI measures whether a skill, prompt, or harness makes a coding agent more creative.
It runs the same agent with (B) and without (A) the change on 24 tasks, has a judge from a
different model family compare the two outputs blind, and reports one number:

- **50** = no difference
- **above 50** = B is more creative

## Axes

| axis | what it measures | how it is judged |
|---|---|---|
| solve | finding a working approach when the obvious one is ruled out | hidden tests first; if both pass, the judge picks the more original approach |
| diverge | generating varied, non-obvious ideas | the judge picks the more varied and less obvious list |
| make | novel artifacts (stories, games, pages) | requirements first; then the judge picks the more novel one |

Each axis has 4 `dev` tasks (use these while building a skill) and 4 `holdout` tasks
(report these). The index is the mean of the three axis win rates, with a 95% bootstrap
confidence interval over tasks.

## Quick start

Requires [uv](https://docs.astral.sh/uv/), Python 3.11+, Claude Code, and Codex CLI.

```bash
cd bench
uv run pytest                          # zero-cost self-test
uv run aci doctor configs/claude-base.yaml   # confirm the baseline runs without your global setup
```

Compare a skill against the baseline:

```bash
uv run aci run --config configs/claude-base.yaml --config configs/claude-skill.yaml --split holdout -k 3 -j 3 --out runs/my-skill
uv run aci judge runs/my-skill --a claude-base --b claude-skill --judge configs/judge-codex.yaml -j 3
uv run aci score runs/my-skill --split holdout
```

The report lands in `runs/my-skill/report.md` and `report.json`. All steps resume where they
stopped.

## Fair comparison

- **Isolation.** The baseline must not load your global plugins, CLAUDE.md, hooks, or MCP
  servers. Run `aci doctor` on every agent config. See `docs/isolation.md`.
- **Blind, swapped judging.** Each pair is judged twice with the order swapped; only a
  consistent preference counts as a win.
- **Different judge family.** Claude agents are judged by Codex by default. The report warns
  when the judge and an agent share a family.
- **dev vs holdout.** Tune on `dev`. Report `holdout`.
- **A/A check.** Run the same config as A and B; the index CI should contain 50.
  See `docs/results/`.

## Configs

An agent or judge is a shell command template in YAML:

```yaml
name: claude-skill
cmd: claude -p --plugin-dir {repo_root} --dangerously-skip-permissions < {prompt_file}
timeout: 900
env: {}
```

Agent placeholders: `{prompt_file}`, `{workdir}`, `{repo_root}`, `{output}`. Judge
placeholders: `{judge_prompt_file}`, `{verdict_file}`. Commands run in a fresh temporary
directory; hidden tests are copied in only after the agent finishes.

## Adding tasks

Add `bench/tasks/<axis>/<id>/task.yaml`:

```yaml
id: diverge-example
axis: diverge          # solve | diverge | make
split: dev             # dev | holdout
output: ideas.md       # file or folder the agent must produce
prompt: |
  ...
check: "{python} -m pytest -q tests"   # solve only
```

Solve tasks also need `starter/`, `tests/`, `reference.py`, and `obvious.py`;
`uv run pytest` checks that the reference passes and the obvious solution fails.

## License

AGPL-3.0-or-later
````

- [ ] **Step 3: 전체 테스트와 커밋**

Run: `cd bench && uv run pytest -q`
Expected: 40 passed

```bash
git add README.md LICENSE
git commit -m "docs: README and license"
```
