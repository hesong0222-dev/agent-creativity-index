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
    assert not has(ast.JoinedStr, ast.Import, ast.ImportFrom)
    assert not NAMES & {"bin", "format"}
    assert "format" not in ATTRS


def test_values():
    rng = random.Random(5)
    assert solution.to_binary(0) == "0"
    assert solution.to_binary(1) == "1"
    assert solution.to_binary(2) == "10"
    assert solution.to_binary(255) == "11111111"
    assert solution.to_binary(2 ** 127) == "1" + "0" * 127
    for _ in range(300):
        n = rng.randrange(2 ** rng.randint(1, 128))
        assert solution.to_binary(n) == "{:b}".format(n)


def test_no_dynamic_code():
    assert not NAMES & {"eval", "exec", "compile", "getattr", "setattr", "__import__", "globals", "locals", "vars", "open"}
