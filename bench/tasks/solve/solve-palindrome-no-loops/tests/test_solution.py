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
    assert "reversed" not in NAMES and "reverse" not in ATTRS
    assert not any(isinstance(n, ast.Slice) and n.step is not None for n in NODES)


def test_values():
    assert solution.is_palindrome("A man, a plan, a canal: Panama")
    assert solution.is_palindrome("")
    assert solution.is_palindrome("No 'x' in Nixon")
    assert not solution.is_palindrome("palindrome")
    assert solution.is_palindrome("ab" * 100 + "ba" * 100)
    assert not solution.is_palindrome("ab" * 200)


def test_no_dynamic_code():
    assert not NAMES & {"eval", "exec", "compile", "getattr", "setattr", "__import__", "globals", "locals", "vars", "open"}
