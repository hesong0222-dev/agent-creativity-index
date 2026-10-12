from collections import Counter

from aci.tasks import AXES, SPLITS, load_tasks


def test_shipped_task_set_shape():
    tasks = load_tasks()
    assert len(tasks) == 24
    assert Counter((t.axis, t.split) for t in tasks) == {(a, s): 4 for a in AXES for s in SPLITS}
