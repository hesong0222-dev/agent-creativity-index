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
