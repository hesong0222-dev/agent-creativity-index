# Agent Creativity Index (ACI)

ACI measures whether a skill, prompt, or harness makes a coding agent more creative.
It runs the same agent with (B) and without (A) the change on 24 tasks, has a judge from a
different model family compare the two outputs blind, and reports one number:

- **50** = no difference
- **above 50** = B is more creative

## Axes

| axis | what it measures | how it is judged |
|---|---|---|
| solve | finding a working approach when the obvious one is ruled out | hidden tests first; if both pass, the judge picks the more original approach |
| diverge | generating varied, non-obvious ideas | the judge picks the more varied and less obvious list |
| make | novel artifacts (stories, games, pages) | requirements first; then the judge picks the more novel one |

Each axis has 4 `dev` tasks (use these while building a skill) and 4 `holdout` tasks
(report these). The index is the mean of the three axis win rates, with a 95% bootstrap
confidence interval over tasks.

## Quick start

Requires [uv](https://docs.astral.sh/uv/), Python 3.11+, Claude Code, and Codex CLI.

```bash
cd bench
uv run pytest                          # zero-cost self-test
uv run aci doctor configs/claude-base.yaml   # confirm the baseline runs without your global setup
```

Compare a skill against the baseline:

```bash
uv run aci run --config configs/claude-base.yaml --config configs/claude-skill.yaml --split holdout -k 3 -j 3 --out runs/my-skill
uv run aci judge runs/my-skill --a claude-base --b claude-skill --judge configs/judge-codex.yaml -j 3
uv run aci score runs/my-skill --split holdout
```

The report lands in `runs/my-skill/report.md` and `report.json`. All steps resume where they
stopped.

## Fair comparison

- **Isolation.** The baseline must not load your global plugins, CLAUDE.md, hooks, or MCP
  servers. Run `aci doctor` on every agent config. See `docs/isolation.md`.
- **Blind, swapped judging.** Each pair is judged twice with the order swapped; only a
  consistent preference counts as a win.
- **Different judge family.** Claude agents are judged by Codex by default. The report warns
  when the judge and an agent share a family.
- **dev vs holdout.** Tune on `dev`. Report `holdout`.
- **A/A check.** Run the same config as A and B; the index CI should contain 50.
  See `docs/results/`.

## Configs

An agent or judge is a shell command template in YAML:

```yaml
name: claude-skill
cmd: claude -p --plugin-dir {plugin_dir} --dangerously-skip-permissions < {prompt_file}
timeout: 900
env: {}
```

Agent placeholders: `{prompt_file}`, `{workdir}`, `{repo_root}`, `{output}`, and `{plugin_dir}` (a temporary copy of only `.claude-plugin/` and `skills/`, so the agent never sees the tasks or answers). Judge
placeholders: `{judge_prompt_file}`, `{verdict_file}`. Commands run in a fresh temporary
directory; hidden tests are copied in only after the agent finishes.

## Adding tasks

Add `bench/tasks/<axis>/<id>/task.yaml`:

```yaml
id: diverge-example
axis: diverge          # solve | diverge | make
split: dev             # dev | holdout
output: ideas.md       # file or folder the agent must produce
prompt: |
  ...
check: "{python} -m pytest -q tests"   # solve only
```

Solve tasks also need `starter/`, `tests/`, `reference.py`, and `obvious.py`;
`uv run pytest` checks that the reference passes and the obvious solution fails.

## License

AGPL-3.0-or-later
