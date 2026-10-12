import ast
import math
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
    assert not has(ast.Mod, ast.FloorDiv, ast.Import, ast.ImportFrom)
    assert "divmod" not in NAMES


def test_values():
    rng = random.Random(4)
    assert solution.gcd(1, 1) == 1
    assert solution.gcd(12, 18) == 6
    assert solution.gcd(17, 5) == 1
    assert solution.gcd(1_000_000, 1_000_000) == 1_000_000
    assert solution.gcd(1_000_000, 3) == 1
    assert solution.gcd(2 ** 19, 3 * 2 ** 10) == 2 ** 10
    for _ in range(100):
        k = rng.randint(1, 1000)
        a, b = k * rng.randint(1, 1000), k * rng.randint(1, 1000)
        assert solution.gcd(a, b) == math.gcd(a, b)


def test_no_dynamic_code():
    assert not NAMES & {"eval", "exec", "compile", "getattr", "setattr", "__import__", "globals", "locals", "vars", "open"}
