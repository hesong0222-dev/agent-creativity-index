import ast
import random
from pathlib import Path

import solution

TREE = ast.parse((Path(__file__).resolve().parent.parent / "solution.py").read_text())
NODES = list(ast.walk(TREE))
NAMES = {n.id for n in NODES if isinstance(n, ast.Name)}
ATTRS = {n.attr for n in NODES if isinstance(n, ast.Attribute)}


def has(*types):
    return any(isinstance(n, types) for n in NODES)


def expected(items):
    out = []
    for item in items:
        if item not in out:
            out.append(item)
    return out


def test_constraints():
    assert not has(ast.Set, ast.SetComp, ast.Import, ast.ImportFrom)
    assert not NAMES & {"set", "frozenset"}
    assert "fromkeys" not in ATTRS


def test_values():
    assert solution.unique([]) == []
    assert solution.unique([3, 1, 3, 2, 1]) == [3, 1, 2]
    assert solution.unique([0, -0, 5, -5]) == [0, 5, -5]
    rng = random.Random(8)
    for size in (1, 10, 100, 5000):
        items = [rng.randint(-50, 50) for _ in range(size)]
        original = list(items)
        assert solution.unique(items) == expected(items)
        assert items == original


def test_no_dynamic_code():
    assert not NAMES & {"eval", "exec", "compile", "getattr", "setattr", "__import__", "globals", "locals", "vars", "open"}
