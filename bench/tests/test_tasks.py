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
