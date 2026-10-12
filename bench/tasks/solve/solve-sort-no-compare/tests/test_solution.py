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
    assert not has(ast.Compare, ast.Import, ast.ImportFrom)
    assert not NAMES & {"sorted", "min", "max"}
    assert "sort" not in ATTRS


def test_sorts_random_lists():
    rng = random.Random(7)
    for size in (0, 1, 2, 50, 10_000):
        nums = [rng.randint(0, 1000) for _ in range(size)]
        assert solution.sort_numbers(list(nums)) == sorted(nums)


def test_duplicates_and_bounds():
    assert solution.sort_numbers([1000, 0, 1000, 0, 5]) == [0, 0, 5, 1000, 1000]


def test_no_dynamic_code():
    assert not NAMES & {"eval", "exec", "compile", "getattr", "setattr", "__import__", "globals", "locals", "vars", "open"}
