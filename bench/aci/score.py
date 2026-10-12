from __future__ import annotations

import json
import random
import shlex
from pathlib import Path

from .judge import read_jsonl
from .tasks import AXES, Task

POINTS = {"B": 1.0, "tie": 0.5, "A": 0.0}


def win_rate(scores: list[float]) -> float | None:
    return 100 * sum(scores) / len(scores) if scores else None


def _interval(values: list[float]) -> tuple[float, float]:
    values = sorted(values)
    return values[int(0.025 * (len(values) - 1))], values[int(0.975 * (len(values) - 1))]


def bootstrap(by_axis: dict[str, dict[str, list[float]]], n: int = 2000, seed: int = 0):
    """Resample tasks with replacement inside each axis. Returns ({axis: ci}, index_ci)."""
    if not by_axis:
        return {}, None
    rng = random.Random(seed)
    axis_draws: dict[str, list[float]] = {axis: [] for axis in by_axis}
    index_draws = []
    for _ in range(n):
        rates = []
        for axis, tasks in by_axis.items():
            ids = sorted(tasks)
            rate = win_rate([s for _ in ids for s in tasks[rng.choice(ids)]])
            axis_draws[axis].append(rate)
            rates.append(rate)
        index_draws.append(sum(rates) / len(rates))
    return {axis: _interval(d) for axis, d in axis_draws.items()}, _interval(index_draws)


def family(cmd: str) -> str:
    for token in shlex.split(cmd):
        if "=" not in token:
            return Path(token).name
    return ""


def summarize(run_dir: Path, tasks: list[Task], n_boot: int = 2000, seed: int = 0) -> dict:
    by_axis: dict[str, dict[str, list[float]]] = {}
    counts = {axis: {"pairs": 0, "judged": 0, "B": 0, "A": 0, "tie": 0, "parse_failures": 0, "failed_pairs": 0}
              for axis in AXES}
    judge_path = run_dir / "judge.json"
    judge = json.loads(judge_path.read_text()) if judge_path.exists() else {}
    want = {k: judge[k] for k in ("a", "b") if k in judge}
    if "name" in judge:
        want["judge"] = judge["name"]
    for task in tasks:
        # only verdicts for the pairing and judge in judge.json; later records override earlier ones
        latest = {r["sample"] if "sample" in r else i: r
                  for i, r in enumerate(read_jsonl(run_dir / task.id / "judgments.jsonl"))
                  if all(r.get(k, v) == v for k, v in want.items())}
        c = counts[task.axis]
        c["failed_pairs"] += sum(1 for r in latest.values() if not r["winner"])
        records = [r for r in latest.values() if r["winner"]]
        if not records:
            continue
        for r in records:
            c["pairs"] += 1
            c[r["winner"]] += 1
            c["judged"] += 0 if r["auto"] else 1
            c["parse_failures"] += r.get("parse_failures", 0)
        by_axis.setdefault(task.axis, {})[task.id] = [POINTS[r["winner"]] for r in records]
    axis_ci, index_ci = bootstrap(by_axis, n_boot, seed)
    axes = {}
    for axis in AXES:
        scores = [s for v in by_axis.get(axis, {}).values() for s in v]
        axes[axis] = {**counts[axis], "rate": win_rate(scores), "ci": axis_ci.get(axis)}
    rates = [a["rate"] for a in axes.values() if a["rate"] is not None]
    summary = {"index": sum(rates) / len(rates) if rates else None, "index_ci": index_ci,
               "axes": axes, "runs": _run_stats(run_dir, tasks)}
    summary["warnings"] = _warnings(run_dir, summary)
    return summary


def _run_stats(run_dir: Path, tasks: list[Task]) -> dict:
    stats: dict[str, dict] = {}
    for task in tasks:
        for meta_path in sorted((run_dir / task.id).glob("*/*/meta.json")):
            m = json.loads(meta_path.read_text())
            s = stats.setdefault(m["config"], {"samples": 0, "failed": 0, "timed_out": 0, "no_output": 0,
                                               "solve_samples": 0, "solve_passed": 0})
            s["samples"] += 1
            s["failed"] += int(m["exit_code"] != 0)
            s["timed_out"] += int(m["timed_out"])
            s["no_output"] += int(not m["has_output"])
            if m["passed"] is not None:
                s["solve_samples"] += 1
                s["solve_passed"] += int(m["passed"])
    return stats


def _warnings(run_dir: Path, summary: dict) -> list[str]:
    out = []
    failed = sum(v["failed_pairs"] for v in summary["axes"].values())
    if failed:
        out.append(f"{failed} pairs could not be judged (judge gave no verdict); re-run `aci judge` to retry them")
    missing = [axis for axis, v in summary["axes"].items() if v["pairs"] == 0]
    if missing:
        out.append(f"no judgments for axes: {', '.join(missing)}; the index averages the rest")
    for axis, v in summary["axes"].items():
        if v["judged"] and v["parse_failures"] / (2 * v["judged"]) > 0.10:
            out.append(f"{axis}: judge failures above 10% of calls")
    configs_path, judge_path = run_dir / "configs.json", run_dir / "judge.json"
    configs = json.loads(configs_path.read_text()) if configs_path.exists() else {}
    judge = json.loads(judge_path.read_text()) if judge_path.exists() else None
    if judge and family(judge["cmd"]) in {family(cmd) for cmd in configs.values()}:
        out.append(f"judge and agent share a model family ({family(judge['cmd'])}); self-preference bias possible")
    return out


def _fmt(rate: float | None, ci) -> str:
    if rate is None:
        return "n/a"
    return f"{rate:.1f} [{ci[0]:.1f}, {ci[1]:.1f}]" if ci else f"{rate:.1f}"


def render_markdown(summary: dict, split: str) -> str:
    lines = [f"# Agent Creativity Index ({split})", "",
             f"**Index: {_fmt(summary['index'], summary['index_ci'])}** (50 = no difference, above 50 = B more creative)", "",
             "| axis | B win rate [95% CI] | pairs | B | A | tie | judged | judge failures |",
             "|---|---|---|---|---|---|---|---|"]
    for axis, v in summary["axes"].items():
        lines.append(f"| {axis} | {_fmt(v['rate'], v['ci'])} | {v['pairs']} | {v['B']} | {v['A']} | {v['tie']} "
                     f"| {v['judged']} | {v['parse_failures']} |")
    lines += ["", "| config | samples | failed | timed out | no output | solve passed |", "|---|---|---|---|---|---|"]
    for name, s in summary["runs"].items():
        solve = f"{s['solve_passed']}/{s['solve_samples']}" if s["solve_samples"] else "n/a"
        lines.append(f"| {name} | {s['samples']} | {s['failed']} | {s['timed_out']} | {s['no_output']} | {solve} |")
    if summary["warnings"]:
        lines += ["", "## Warnings", ""] + [f"- {w}" for w in summary["warnings"]]
    return "\n".join(lines) + "\n"
