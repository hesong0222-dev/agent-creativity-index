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
    assert not has(ast.For, ast.While, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp,
                   ast.Import, ast.ImportFrom)
    assert "count" not in ATTRS and "sum" not in NAMES


def test_values():
    assert solution.count_vowels("") == 0
    assert solution.count_vowels("rhythm") == 0
    assert solution.count_vowels("AEIOU aeiou") == 10
    assert solution.count_vowels("Hello, World!") == 3
    assert solution.count_vowels("The quick brown fox jumps over the lazy dog. " * 50) == 11 * 50


def test_no_dynamic_code():
    assert not NAMES & {"eval", "exec", "compile", "getattr", "setattr", "__import__", "globals", "locals", "vars", "open"}
