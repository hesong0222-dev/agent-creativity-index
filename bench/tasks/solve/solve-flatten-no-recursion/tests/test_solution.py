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


def expected(nested):
    out = []
    for item in nested:
        out.extend(expected(item) if isinstance(item, list) else [item])
    return out


def test_constraints():
    funcs = [n for n in NODES if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    assert [f.name for f in funcs] == ["flatten"]
    assert not has(ast.ClassDef, ast.Lambda, ast.Import, ast.ImportFrom)
    assert "flatten" not in NAMES


def test_values():
    assert solution.flatten([]) == []
    assert solution.flatten([[], [[]], [[[]]]]) == []
    assert solution.flatten([1, [2, [3, [4]], 5], [], -6]) == [1, 2, 3, 4, 5, -6]
    deep = [7]
    for i in range(49):
        deep = [i, deep, -i]
    assert solution.flatten(deep) == expected(deep)


def test_random():
    rng = random.Random(2)

    def build(depth):
        return [build(depth + 1) if depth < 8 and rng.random() < 0.3 else rng.randint(-99, 99)
                for _ in range(rng.randint(0, 5))]

    for _ in range(200):
        nested = build(0)
        assert solution.flatten(nested) == expected(nested)


def test_no_dynamic_code():
    assert not NAMES & {"eval", "exec", "compile", "getattr", "setattr", "__import__", "globals", "locals", "vars", "open"}
