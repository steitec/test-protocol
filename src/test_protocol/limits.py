"""Limits from a TOML file: set or override limits and re-evaluate PASS/FAIL."""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path

from .model import InputError, Item, Protocol

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

_KEYS = {"step", "measurement", "low", "high", "expect", "unit"}


@dataclass
class Limit:
    measurement: str
    step: str | None = None
    low: float | None = None
    high: float | None = None
    expect: str | None = None
    unit: str | None = None


def _limit(entry: object, where: str) -> Limit:
    if not isinstance(entry, dict):
        raise InputError(f"{where}: must be a table")
    unknown = sorted(set(entry) - _KEYS)
    if unknown:
        raise InputError(f"{where}: unknown key {unknown[0]!r}")
    if not isinstance(entry.get("measurement"), str) or not entry["measurement"].strip():
        raise InputError(f"{where}: missing 'measurement'")
    for key in ("step", "expect", "unit"):
        if key in entry and not isinstance(entry[key], str):
            raise InputError(f"{where}: {key} must be text")
    for key in ("low", "high"):
        if key in entry and (isinstance(entry[key], bool)
                             or not isinstance(entry[key], (int, float))
                             or not math.isfinite(entry[key])):
            raise InputError(f"{where}: {key} must be a finite number")
    low, high = entry.get("low"), entry.get("high")
    if low is None and high is None and "expect" not in entry:
        raise InputError(f"{where}: needs low, high or expect")
    if "expect" in entry and (low is not None or high is not None):
        raise InputError(f"{where}: use either expect or low/high")
    if low is not None and high is not None and low > high:
        raise InputError(f"{where}: low > high ({low} > {high})")
    return Limit(entry["measurement"], entry.get("step"),
                 None if low is None else float(low), None if high is None else float(high),
                 entry.get("expect"), entry.get("unit"))


def load_limits(path: Path) -> list[Limit]:
    path = Path(path)
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as e:
        raise InputError(f"{path.name}: cannot read: {e.strerror or e}") from None
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as e:
        raise InputError(f"{path.name}: invalid TOML: {e}") from None
    unknown = sorted(set(data) - {"limit"})
    if unknown:
        raise InputError(f"{path.name}: unknown table {unknown[0]!r}; expected [[limit]]")
    entries = data.get("limit", [])
    if not isinstance(entries, list):
        raise InputError(f"{path.name}: use [[limit]] tables")
    return [_limit(e, f"{path.name}: limit {n}") for n, e in enumerate(entries, 1)]


def _key(text: str | None) -> str:
    return (text or "").strip().casefold()


def apply_limits(p: Protocol, limits: list[Limit], source: str) -> list[Limit]:
    used: set[int] = set()
    for group in p.groups:
        for item in group.items:
            if item.value is None:
                continue
            candidates = [(n, lim) for n, lim in enumerate(limits)
                          if _key(lim.measurement) == _key(item.name)
                          and (lim.step is None or _key(lim.step) == _key(group.name))]
            if not candidates:
                continue
            # a step-specific limit beats a general one; otherwise the first one wins
            n, lim = sorted(candidates, key=lambda c: c[1].step is None)[0]
            used.add(n)
            _set(item, lim, source)
    return [lim for n, lim in enumerate(limits) if n not in used]


def _set(item: Item, lim: Limit, source: str) -> None:
    item.low, item.high, item.expect = lim.low, lim.high, lim.expect
    if lim.unit is not None:
        item.unit = lim.unit
    item.limit_source = source
    item.message = "" if item.message == "value is not a number" else item.message
    item.evaluate()


def require_limits(p: Protocol) -> None:
    for item in p.items():
        if item.value is not None and not item.has_limits():
            item.status = "FAIL"
            item.message = "no limit defined"
