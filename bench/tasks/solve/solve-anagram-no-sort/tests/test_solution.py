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
    assert "sorted" not in NAMES
    assert "sort" not in ATTRS


def test_values():
    assert solution.is_anagram("", "")
    assert solution.is_anagram("listen", "silent")
    assert solution.is_anagram("a gentleman", "elegant man")
    assert not solution.is_anagram("Listen", "silent")
    assert not solution.is_anagram("aab", "abb")
    assert not solution.is_anagram("abc", "abcd")
    assert not solution.is_anagram("ab ", "ab")
    rng = random.Random(9)
    for _ in range(300):
        a = "".join(rng.choice("abcAB !") for _ in range(rng.randint(0, 12)))
        b = list(a)
        rng.shuffle(b)
        if rng.random() < 0.5 and b:
            b[rng.randrange(len(b))] = rng.choice("abcAB !")
        b = "".join(b)
        assert solution.is_anagram(a, b) == (sorted(a) == sorted(b))


def test_no_dynamic_code():
    assert not NAMES & {"eval", "exec", "compile", "getattr", "setattr", "__import__", "globals", "locals", "vars", "open"}
