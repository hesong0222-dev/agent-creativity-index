import ast
import random
from pathlib import Path

import solution

TREE = ast.parse((Path(__file__).resolve().parent.parent / "solution.py").read_text())
NODES = list(ast.walk(TREE))
NAMES = {n.id for n in NODES if isinstance(n, ast.Name)}
ATTRS = {n.attr for n in NODES if isinstance(n, ast.Attribute)}
ARITH = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.MatMult)


def has(*types):
    return any(isinstance(n, types) for n in NODES)


def test_constraints():
    assert not any(isinstance(n, (ast.BinOp, ast.AugAssign)) and isinstance(n.op, ARITH) for n in NODES)
    assert not any(isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub) for n in NODES)
    assert not has(ast.Import, ast.ImportFrom)
    assert "sum" not in NAMES
    assert not any("add" in a or "sub" in a for a in ATTRS)


def test_values():
    rng = random.Random(11)
    assert solution.add(0, 0) == 0
    assert solution.add(10**6, 10**6) == 2 * 10**6
    for _ in range(500):
        a, b = rng.randint(0, 10**6), rng.randint(0, 10**6)
        assert solution.add(a, b) == a + b


def test_no_dynamic_code():
    assert not NAMES & {"eval", "exec", "compile", "getattr", "setattr", "__import__", "globals", "locals", "vars", "open"}
