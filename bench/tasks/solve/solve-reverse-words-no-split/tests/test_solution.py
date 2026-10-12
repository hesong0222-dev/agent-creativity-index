import ast
from pathlib import Path

import solution

TREE = ast.parse((Path(__file__).resolve().parent.parent / "solution.py").read_text())
NODES = list(ast.walk(TREE))
NAMES = {n.id for n in NODES if isinstance(n, ast.Name)}
ATTRS = {n.attr for n in NODES if isinstance(n, ast.Attribute)}


def has(*types):
    return any(isinstance(n, types) for n in NODES)


def test_constraints():
    assert not has(ast.Import, ast.ImportFrom)
    assert not ATTRS & {"split", "rsplit", "partition", "rpartition", "reverse"}
    assert "reversed" not in NAMES
    assert not any(isinstance(n, ast.Slice) and n.step is not None for n in NODES)


def test_values():
    assert solution.reverse_words("the quick brown fox") == "fox brown quick the"
    assert solution.reverse_words("  hello   world  ") == "world hello"
    assert solution.reverse_words("single") == "single"
    assert solution.reverse_words("") == ""
    assert solution.reverse_words("   ") == ""
