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
    assert not has(ast.JoinedStr, ast.Mod, ast.Import, ast.ImportFrom)
    assert not NAMES & {"str", "repr", "ascii", "format"}
    assert not ATTRS & {"format", "__str__", "__repr__", "__format__"}


def test_values():
    rng = random.Random(11)
    assert solution.digit_sum(0) == 0
    assert solution.digit_sum(7) == 7
    assert solution.digit_sum(10) == 1
    assert solution.digit_sum(99999) == 45
    for _ in range(200):
        n = rng.randint(0, 10 ** rng.randint(1, 300))
        assert solution.digit_sum(n) == sum(map(int, "%d" % n))


def test_no_dynamic_code():
    assert not NAMES & {"eval", "exec", "compile", "getattr", "setattr", "__import__", "globals", "locals", "vars", "open"}
