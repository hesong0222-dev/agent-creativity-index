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
