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
