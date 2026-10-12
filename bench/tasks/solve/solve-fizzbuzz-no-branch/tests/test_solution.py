import ast
from pathlib import Path

import solution

TREE = ast.parse((Path(__file__).resolve().parent.parent / "solution.py").read_text())
NODES = list(ast.walk(TREE))
NAMES = {n.id for n in NODES if isinstance(n, ast.Name)}
ATTRS = {n.attr for n in NODES if isinstance(n, ast.Attribute)}


def has(*types):
    return any(isinstance(n, types) for n in NODES)


def expected(n):
    out = []
    for i in range(1, n + 1):
        out.append("FizzBuzz" if i % 15 == 0 else "Fizz" if i % 3 == 0 else "Buzz" if i % 5 == 0 else str(i))
    return out


def test_constraints():
    assert not has(ast.If, ast.IfExp, ast.Match, ast.BoolOp, ast.Compare, ast.Import, ast.ImportFrom)
    assert not any(isinstance(n, ast.comprehension) and n.ifs for n in NODES)


def test_values():
    assert solution.fizzbuzz(15)[-1] == "FizzBuzz"
    for n in (0, 1, 15, 100):
        assert solution.fizzbuzz(n) == expected(n)
