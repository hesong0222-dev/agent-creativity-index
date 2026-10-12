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


def expected(text):
    words = text.split()
    return max(words, key=words.count)


def test_constraints():
    assert not has(ast.Dict, ast.DictComp, ast.Import, ast.ImportFrom)
    assert "dict" not in NAMES
    assert "count" not in ATTRS


def test_values():
    assert solution.top_word("solo") == "solo"
    assert solution.top_word("b a b a c") == "b"
    assert solution.top_word("  x  y  y   x z y ") == "y"
    assert solution.top_word("one two three") == "one"
    rng = random.Random(12)
    for _ in range(300):
        text = (" " * rng.randint(1, 3)).join(rng.choice(["ant", "bee", "cat", "dog", "eel"])
                                              for _ in range(rng.randint(1, 30)))
        assert solution.top_word(text) == expected(text)


def test_no_dynamic_code():
    assert not NAMES & {"eval", "exec", "compile", "getattr", "setattr", "__import__", "globals", "locals", "vars", "open"}
