"""JSON subset helpers for data-driven expectations (story 05 tests)."""

from __future__ import annotations


def assert_subset(actual, expected, where: str = "$") -> None:
    """Recursive subset check: dicts by key, lists element by element (same length), scalars equal."""
    if isinstance(expected, dict):
        assert isinstance(actual, dict), f"{where}: {actual!r} is not a mapping"
        for key, value in expected.items():
            assert key in actual, f"{where}.{key} missing"
            assert_subset(actual[key], value, f"{where}.{key}")
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected), f"{where}: {actual!r} != {expected!r}"
        for position, (a, e) in enumerate(zip(actual, expected, strict=True)):
            assert_subset(a, e, f"{where}[{position}]")
    else:
        assert actual == expected, f"{where}: {actual!r} != {expected!r}"


def has_path(data, path: str) -> bool:
    """True when the dotted path (list positions as integers) exists in the JSON-like data."""
    current = data
    for part in path.split("."):
        if isinstance(current, list):
            if not part.isdigit() or int(part) >= len(current):
                return False
            current = current[int(part)]
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return False
    return True
