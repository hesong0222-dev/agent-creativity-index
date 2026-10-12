import json

from aci.adapter import Config
from aci.doctor import default_forbid, doctor, find_hits


def test_default_forbid_collects_user_level_items(tmp_path):
    claude = tmp_path / ".claude"
    (claude / "plugins").mkdir(parents=True)
    (claude / "plugins" / "installed_plugins.json").write_text(json.dumps({"version": 2, "plugins": {
        "superpowers@x": [], "code-review@x": [], "agent-creativity-index@y": []}}))
    (claude / "skills" / "factchk").mkdir(parents=True)
    (claude / "agents").mkdir()
    (claude / "agents" / "oxalpha-planner.md").write_text("x")
    forbid = default_forbid(home=tmp_path)
    assert {"superpowers", "factchk", "oxalpha-planner", "code-review:"} <= set(forbid)
    assert "agent-creativity-index" not in forbid and "code-review" not in forbid  # built-in name
    assert str(claude / "CLAUDE.md") in forbid


def test_find_hits_matches_whole_names_only():
    assert find_hits("Loaded: SuperPowers skill", ["superpowers", "omc"]) == ["superpowers"]
    assert find_hits("a gossip column", ["sip"]) == []
    assert find_hits("- code-review (built-in)", ["code-review:"]) == []
    assert find_hits("- code-review:code-review", ["code-review:"]) == ["code-review:"]
    assert find_hits("read /home/u/.claude/CLAUDE.md\n", ["/home/u/.claude/CLAUDE.md"]) == ["/home/u/.claude/CLAUDE.md"]


def test_doctor_with_fake_agent(tmp_path):
    hits, inventory = doctor(Config(name="fake", cmd="echo 'skills: none' > {output}"), tmp_path, ["superpowers"])
    assert hits == [] and "skills: none" in inventory
