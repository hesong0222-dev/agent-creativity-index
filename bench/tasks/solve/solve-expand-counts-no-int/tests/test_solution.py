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
    assert "int" not in NAMES
    assert not ATTRS & {"isdigit", "isdecimal", "isnumeric"}


def test_values():
    assert solution.expand("") == ""
    assert solution.expand("a1") == "a"
    assert solution.expand("a3b12c1") == "aaa" + "b" * 12 + "c"
    assert solution.expand("z10") == "z" * 10
    assert solution.expand("a2a3") == "aaaaa"
    rng = random.Random(1)
    for _ in range(200):
        groups = [(rng.choice("abcxyz"), rng.randint(1, 300)) for _ in range(rng.randint(0, 6))]
        code = "".join(f"{c}{k}" for c, k in groups)
        assert solution.expand(code) == "".join(c * k for c, k in groups)


def test_no_dynamic_code():
    assert not NAMES & {"eval", "exec", "compile", "getattr", "setattr", "__import__", "globals", "locals", "vars", "open"}
