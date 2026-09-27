"""Assertion evaluation shared by pipeline ``assert`` nodes and test cases.

An assertion spec is a plain JSON object (stored in ``TestCaseNode.assertions``
or an ``assert`` pipeline node's ``config``). Each recognised key is one check
against a single target string (the pipeline's text output). Every check present
must hold for the spec to pass.

Supported checks::

    {
        "equals":       "exact string",
        "iequals":      "case-insensitive exact string",
        "contains":     "substring that must appear",
        "not_contains": "substring that must NOT appear",
        "regex":        "python regex that must search-match",
        "min_length":   10,
        "max_length":   500
    }

Unknown keys are reported (``passed=False``) rather than silently ignored, so a
typo in a spec surfaces as a failing check instead of a always-green test.
"""

import re
from typing import Any


def _check(op: str, expected: Any, target: str) -> bool:
    if op == "equals":
        return target == expected
    if op == "iequals":
        return target.casefold() == str(expected).casefold()
    if op == "contains":
        return str(expected) in target
    if op == "not_contains":
        return str(expected) not in target
    if op == "regex":
        return re.search(str(expected), target) is not None
    if op == "min_length":
        return len(target) >= int(expected)
    if op == "max_length":
        return len(target) <= int(expected)
    raise KeyError(op)


def evaluate_assertions(assertions: dict, target: str) -> tuple[bool, list[dict]]:
    """Evaluate every check in ``assertions`` against ``target``.

    Returns ``(passed, checks)`` where ``passed`` is True only if every check
    passed, and ``checks`` is a per-check breakdown suitable for persisting to a
    run's result JSON.
    """
    checks: list[dict] = []
    target = target or ""

    if not assertions:
        # No checks means nothing to prove — treat as a vacuous pass, but say so.
        return True, [{"op": "noop", "passed": True, "detail": "no assertions"}]

    all_passed = True
    for op, expected in assertions.items():
        try:
            ok = _check(op, expected, target)
            checks.append({"op": op, "expected": expected, "passed": ok})
        except KeyError:
            ok = False
            checks.append(
                {"op": op, "expected": expected, "passed": False,
                 "detail": f"unknown assertion '{op}'"}
            )
        except (re.error, ValueError, TypeError) as exc:
            ok = False
            checks.append(
                {"op": op, "expected": expected, "passed": False,
                 "detail": f"invalid assertion: {exc}"}
            )
        all_passed = all_passed and ok

    return all_passed, checks
