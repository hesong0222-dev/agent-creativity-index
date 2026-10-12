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


def expected(s):
    stack = []
    for ch in s:
        if ch in "([{":
            stack.append(ch)
        elif ch in ")]}":
            if not stack or stack.pop() + ch not in ("()", "[]", "{}"):
                return False
    return not stack


def test_constraints():
    assert not has(ast.List, ast.ListComp, ast.Import, ast.ImportFrom)
    assert "list" not in NAMES
    assert not ATTRS & {"append", "pop"}


def test_values():
    assert solution.balanced("")
    assert solution.balanced("no brackets here")
    assert solution.balanced("f(a[i], {k: v})")
    assert not solution.balanced("(]")
    assert not solution.balanced("([)]")
    assert not solution.balanced("(((")
    assert not solution.balanced("}")
    rng = random.Random(6)
    for _ in range(500):
        s = "".join(rng.choice("()[]{}x") for _ in range(rng.randint(0, 14)))
        assert solution.balanced(s) == expected(s)


def test_no_dynamic_code():
    assert not NAMES & {"eval", "exec", "compile", "getattr", "setattr", "__import__", "globals", "locals", "vars", "open"}
