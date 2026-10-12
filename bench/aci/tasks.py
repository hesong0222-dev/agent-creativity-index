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
