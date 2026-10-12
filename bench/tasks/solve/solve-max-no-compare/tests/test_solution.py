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
    assert not has(ast.Compare, ast.If, ast.IfExp, ast.BoolOp, ast.Import, ast.ImportFrom)
    assert not NAMES & {"max", "min", "sorted"}
    assert "sort" not in ATTRS


def test_values():
    rng = random.Random(3)
    assert solution.largest([5]) == 5
    assert solution.largest([-3, -1, -2]) == -1
    for _ in range(200):
        vals = [rng.randint(-10**9, 10**9) for _ in range(rng.randint(1, 50))]
        assert solution.largest(vals) == max(vals)
