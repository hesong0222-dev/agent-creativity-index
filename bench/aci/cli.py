from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .adapter import load_config
from .doctor import default_forbid, doctor
from .judge import judge_run
from .runner import run_all
from .score import render_markdown, summarize
from .tasks import SPLITS, TASKS_ROOT, load_tasks

REPO_ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aci", description="Agent Creativity Index")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run agents on tasks")
    run.add_argument("--config", action="append", required=True, help="agent config yaml; repeat for A and B")
    run.add_argument("--split", choices=SPLITS)
    run.add_argument("--only", help="comma-separated task ids")
    run.add_argument("-k", type=int, default=3, help="samples per task and config")
    run.add_argument("-j", type=int, default=1, help="parallel jobs")
    run.add_argument("--out", required=True)
    run.add_argument("--tasks-dir", default=str(TASKS_ROOT))

    judge = sub.add_parser("judge", help="blind pairwise judging of a run")
    judge.add_argument("run_dir")
    judge.add_argument("--a", required=True, help="baseline config name")
    judge.add_argument("--b", required=True, help="treatment config name")
    judge.add_argument("--judge", required=True, help="judge config yaml")
    judge.add_argument("-j", type=int, default=1)
    judge.add_argument("--tasks-dir", default=str(TASKS_ROOT))

    score = sub.add_parser("score", help="compute the index")
    score.add_argument("run_dir")
    score.add_argument("--split", choices=SPLITS, default="holdout")
    score.add_argument("--tasks-dir", default=str(TASKS_ROOT))
    score.add_argument("--a", help="baseline config name (default: the pair in judge.json)")
    score.add_argument("--b", help="treatment config name (default: the pair in judge.json)")

    doc = sub.add_parser("doctor", help="check that an agent config runs without the user's global setup")
    doc.add_argument("config")
    doc.add_argument("--forbid", action="append", default=[], help="extra marker that must not appear")

    args = parser.parse_args(argv)

    if args.command == "run":
        tasks = load_tasks(Path(args.tasks_dir), args.split)
        if args.only:
            wanted = set(args.only.split(","))
            tasks = [t for t in tasks if t.id in wanted]
        configs = [load_config(Path(c)) for c in args.config]
        run_all(tasks, configs, args.k, Path(args.out), REPO_ROOT, args.j)
        return 0
    if args.command == "judge":
        judge_run(Path(args.run_dir), load_tasks(Path(args.tasks_dir)), args.a, args.b,
                  load_config(Path(args.judge)), args.j)
        return 0
    if args.command == "score":
        run_dir = Path(args.run_dir)
        summary = summarize(run_dir, load_tasks(Path(args.tasks_dir), args.split), a=args.a, b=args.b)
        name = f"report-{args.a}-vs-{args.b}" if args.a and args.b else "report"  # one report per pair
        (run_dir / f"{name}.json").write_text(json.dumps({"split": args.split, "a": args.a, "b": args.b, **summary}, indent=2))
        markdown = render_markdown(summary, args.split)
        (run_dir / f"{name}.md").write_text(markdown)
        print(markdown)
        return 0
    hits, inventory = doctor(load_config(Path(args.config)), REPO_ROOT, default_forbid() + args.forbid)
    print(inventory or "(no inventory.txt produced)")
    if not inventory:
        print("FAIL: the agent produced no inventory", file=sys.stderr)
        return 2
    if hits:
        print(f"FAIL: global items leaked into the session: {', '.join(hits)}", file=sys.stderr)
        return 1
    print("PASS: no global items detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
