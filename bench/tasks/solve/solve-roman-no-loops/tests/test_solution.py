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
    out = ""
    for value, symbol in ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
                          (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        count, n = divmod(n, value)
        out += symbol * count
    return out


def test_constraints():
    assert not has(ast.For, ast.AsyncFor, ast.While, ast.comprehension, ast.Import, ast.ImportFrom)


def test_values():
    assert solution.to_roman(1) == "I"
    assert solution.to_roman(4) == "IV"
    assert solution.to_roman(1994) == "MCMXCIV"
    assert solution.to_roman(3999) == "MMMCMXCIX"
    for n in range(1, 4000):
        assert solution.to_roman(n) == expected(n)


def test_no_dynamic_code():
    assert not NAMES & {"eval", "exec", "compile", "getattr", "setattr", "__import__", "globals", "locals", "vars", "open"}
