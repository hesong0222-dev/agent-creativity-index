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
