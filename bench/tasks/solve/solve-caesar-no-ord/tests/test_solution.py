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


def expected(text, k):
    return "".join(chr((ord(c) - 97 + k) % 26 + 97) if "a" <= c <= "z" else c for c in text)


def test_constraints():
    assert not has(ast.Import, ast.ImportFrom)
    assert not NAMES & {"ord", "chr"}
    assert not ATTRS & {"translate", "maketrans"}


def test_values():
    assert solution.shift("", 5) == ""
    assert solution.shift("xyz!", 3) == "abc!"
    assert solution.shift("abc", -1) == "zab"
    assert solution.shift("Hello, World", 26) == "Hello, World"
    assert solution.shift("Hello, World", 1) == "Hfmmp, Wpsme"
    rng = random.Random(10)
    for _ in range(300):
        text = "".join(rng.choice("abcxyzABZ 9.-") for _ in range(rng.randint(0, 20)))
        k = rng.randint(-1000, 1000)
        assert solution.shift(text, k) == expected(text, k)


def test_no_dynamic_code():
    assert not NAMES & {"eval", "exec", "compile", "getattr", "setattr", "__import__", "globals", "locals", "vars", "open"}
