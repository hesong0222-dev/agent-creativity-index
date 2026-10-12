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


def test_failed_judgments_and_other_pairings_are_excluded(tmp_path):
    tasks = [Task("m1", "make", "holdout", "p", "o.md", tmp_path)]
    run = tmp_path / "run"
    (run / "m1").mkdir(parents=True)
    rows = [{"winner": None, "auto": False, "parse_failures": 2, "a": "x", "b": "y", "judge": "j"},
            {"winner": "A", "auto": False, "parse_failures": 0, "a": "y", "b": "x", "judge": "j"}]
    (run / "m1" / "judgments.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (run / "judge.json").write_text(json.dumps({"name": "j", "cmd": "codex exec", "a": "x", "b": "y"}))
    s = summarize(run, tasks, n_boot=10)
    assert s["index"] is None and s["axes"]["make"]["failed_pairs"] == 1
    assert any("could not be judged" in w for w in s["warnings"])
