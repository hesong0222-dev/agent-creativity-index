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
