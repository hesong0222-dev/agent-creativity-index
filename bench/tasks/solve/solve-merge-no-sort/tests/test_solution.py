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


def test_constraints():
    assert not has(ast.Import, ast.ImportFrom)
    assert not NAMES & {"sorted", "min", "max"}
    assert "sort" not in ATTRS


def test_values():
    assert solution.merge([], []) == []
    assert solution.merge([1, 2], []) == [1, 2]
    assert solution.merge([], [-1]) == [-1]
    assert solution.merge([1, 3, 5], [2, 3, 6]) == [1, 2, 3, 3, 5, 6]
    rng = random.Random(13)
    for _ in range(200):
        a = sorted(rng.randint(-100, 100) for _ in range(rng.randint(0, 1000)))
        b = sorted(rng.randint(-100, 100) for _ in range(rng.randint(0, 1000)))
        a0, b0 = list(a), list(b)
        assert solution.merge(a, b) == sorted(a + b)
        assert (a, b) == (a0, b0)


def test_no_dynamic_code():
    assert not NAMES & {"eval", "exec", "compile", "getattr", "setattr", "__import__", "globals", "locals", "vars", "open"}
