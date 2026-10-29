"""Normalized result data: every reader produces a Protocol."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

STATUSES = ("PASS", "FAIL", "ERROR", "SKIP", "INFO")
_BAD = ("FAIL", "ERROR")


class InputError(Exception):
    """Bad input or configuration; the CLI reports it and exits with 2."""


def as_number(value: object) -> float | None:
    """The value as a finite float, or None if it is not a number."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


@dataclass
class Item:
    name: str
    status: str | None = None
    value: float | str | None = None
    unit: str = ""
    low: float | None = None
    high: float | None = None
    expect: str | None = None
    message: str = ""
    limit_source: str | None = None

    def has_limits(self) -> bool:
        return self.low is not None or self.high is not None or self.expect is not None

    def evaluate(self) -> None:
        if self.expect is not None:
            self.status = "PASS" if str(self.value).strip() == self.expect.strip() else "FAIL"
        elif self.low is not None or self.high is not None:
            number = as_number(self.value)
            if number is None:
                self.status = "FAIL"
                self.message = "value is not a number"
            elif (self.low is not None and number < self.low) or \
                    (self.high is not None and number > self.high):
                self.status = "FAIL"
            else:
                self.status = "PASS"
        elif self.status is None:
            self.status = "INFO"


@dataclass
class Group:
    name: str
    items: list[Item] = field(default_factory=list)
    status: str | None = None
    message: str = ""
    source: str = ""

    def counts_own_status(self) -> bool:
        """Whether the group status shows up on its own in counts and failures.

        A group without items stands for itself. A failing group whose items all
        pass (a step that failed for a reason outside its measurements) must not
        hide behind them.
        """
        if self.status is None:
            return False
        if not self.items:
            return True
        return self.status in _BAD and not any(i.status in _BAD for i in self.items)


@dataclass
class Attachment:
    title: str
    text: str


@dataclass
class InputFile:
    name: str
    sha256: str
    format: str


@dataclass
class Protocol:
    header: dict[str, str] = field(default_factory=dict)
    groups: list[Group] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)
    inputs: list[InputFile] = field(default_factory=list)

    def items(self) -> list[Item]:
        return [item for group in self.groups for item in group.items]

    def counts(self) -> dict[str, int]:
        counts = dict.fromkeys(STATUSES, 0)
        for group in self.groups:
            if group.counts_own_status():
                counts[group.status] += 1  # type: ignore[index]
            for item in group.items:
                if item.status in counts:
                    counts[item.status] += 1  # type: ignore[index]
        return counts

    def verdict(self) -> str:
        bad = any(g.status in _BAD for g in self.groups) or \
            any(i.status in _BAD for i in self.items())
        return "FAIL" if bad else "PASS"

    def failures(self) -> list[tuple[Group, Item | None]]:
        found: list[tuple[Group, Item | None]] = []
        for group in self.groups:
            if group.counts_own_status() and group.status in _BAD:
                found.append((group, None))
            found.extend((group, item) for item in group.items if item.status in _BAD)
        return found
