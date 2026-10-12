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
