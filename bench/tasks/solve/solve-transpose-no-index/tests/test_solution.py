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
    assert not has(ast.Subscript, ast.Import, ast.ImportFrom)
    assert "zip" not in NAMES


def test_values():
    assert solution.transpose([]) == []
    assert solution.transpose([[7]]) == [[7]]
    assert solution.transpose([[1, 2, 3], [4, 5, 6]]) == [[1, 4], [2, 5], [3, 6]]
    m = [[r * 10 + c for c in range(7)] for r in range(5)]
    assert solution.transpose(m) == [list(col) for col in zip(*m)]
