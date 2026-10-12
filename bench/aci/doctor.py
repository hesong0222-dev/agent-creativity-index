from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

from .adapter import Config
from .runner import run_sample, sample_dir
from .tasks import Task

OWN_PLUGIN = "agent-creativity-index"
# Names Claude Code also ships as built-ins; for these only the plugin-namespaced form ("name:") is a leak.
BUILTIN_NAMES = {"code-review", "security-review", "simplify", "init", "review"}
DOCTOR_PROMPT = (
    "List everything loaded into this session that you can see: skills, plugins, slash commands, "
    "subagents, MCP servers, hooks, and instruction files such as CLAUDE.md (give full paths). "
    "Write the list, one item per line, to inventory.txt in the current directory. Do nothing else."
)


def default_forbid(home: Path | None = None) -> list[str]:
    """Markers of the user's global setup that must not show up in an isolated session."""
    claude = (home or Path.home()) / ".claude"
    markers = ["~/.claude/CLAUDE.md", str(claude / "CLAUDE.md")]
    names: set[str] = set()
    registry = claude / "plugins" / "installed_plugins.json"
    if registry.exists():
        names |= {name.split("@")[0] for name in json.loads(registry.read_text()).get("plugins", {})}
    names |= {p.name for p in (claude / "skills").glob("*") if p.is_dir()}
    names |= {p.stem for p in (claude / "agents").glob("*.md")}
    names |= {p.stem for p in (claude / "commands").glob("*.md")}
    names.discard(OWN_PLUGIN)
    return markers + sorted(f"{n}:" if n in BUILTIN_NAMES else n for n in names)


def find_hits(inventory: str, forbid: list[str]) -> list[str]:
    """Case-insensitive match that will not hit inside a longer name (sip vs gossip)."""
    low = inventory.lower()
    hits = []
    for marker in forbid:
        pattern = re.escape(marker.lower())
        if marker[:1].isalnum():
            pattern = r"(?<![\w-])" + pattern
        if marker[-1:].isalnum():
            pattern += r"(?![\w-])"
        if re.search(pattern, low):
            hits.append(marker)
    return hits


def doctor(config: Config, repo_root: Path, forbid: list[str]) -> tuple[list[str], str]:
    with tempfile.TemporaryDirectory(prefix="aci-doctor-") as tmp:
        task = Task(id="doctor", axis="make", split="dev", prompt=DOCTOR_PROMPT,
                    output="inventory.txt", dir=Path(tmp))
        out = Path(tmp) / "out"
        run_sample(task, config, 0, out, repo_root)
        path = sample_dir(out, "doctor", config.name, 0) / "output" / "inventory.txt"
        inventory = path.read_text() if path.exists() else ""
    return find_hits(inventory, forbid), inventory
