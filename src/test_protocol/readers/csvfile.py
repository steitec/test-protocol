"""CSV with one measurement per row (bench-automation measurements.csv, Excel exports)."""

from __future__ import annotations

import csv
import io

from ..model import STATUSES, Group, InputError, Item, Protocol

COLUMNS = ("serial", "step", "measurement", "value", "unit", "low", "high", "result")


def _header_line(text: str) -> str:
    return text.lstrip("﻿").split("\n", 1)[0]


def _delimiter(line: str) -> str:
    return ";" if line.count(";") > line.count(",") else ","


def matches(text: str) -> bool:
    line = _header_line(text)
    names = {c.strip().lower() for c in line.split(_delimiter(line))}
    return {"measurement", "value"} <= names


def _number(cell: str, decimal_comma: bool) -> float | None:
    s = cell.replace(" ", "").replace(" ", "")
    if decimal_comma and "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def read(text: str, name: str) -> Protocol:
    text = text.lstrip("﻿")
    delimiter = _delimiter(_header_line(text))
    decimal_comma = delimiter == ";"
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    columns = [c.strip().lower() for c in next(reader, [])]
    groups: dict[str, Group] = {}
    serials: list[str] = []
    for row in reader:
        if not any(cell.strip() for cell in row):
            continue
        cells = {col: cell.strip() for col, cell in zip(columns, row) if col in COLUMNS}
        get = lambda col: cells.get(col) or None  # noqa: E731
        value: float | str | None = get("value")
        if value is not None:
            number = _number(value, decimal_comma)
            value = value if number is None else number
        item = Item(cells.get("measurement", ""), value=value, unit=cells.get("unit", ""))
        for bound in ("low", "high"):
            cell = get(bound)
            if cell is None:
                continue
            number = _number(cell, decimal_comma)
            if number is None:
                item.expect = cell          # a text "limit" is the expected text
            else:
                setattr(item, bound, number)
        if item.expect is not None and get("value") is not None:
            item.value = cells["value"]     # a text check compares the cell as written
        result = get("result")
        if result is not None:
            if result.upper() not in STATUSES:
                raise InputError(f"{name}: line {reader.line_num}: unknown result {result!r}")
            item.status = result.upper()
        elif item.has_limits():
            item.evaluate()
        if get("serial") and get("serial") not in serials:
            serials.append(cells["serial"])
        step = get("step") or name
        groups.setdefault(step, Group(step, source=name)).items.append(item)
    if len(serials) > 1:
        raise InputError(f"{name}: several serial numbers ({', '.join(serials)}); "
                         "one protocol per device")
    for group in groups.values():
        for item in group.items:
            if item.status is None:
                item.evaluate()
    return Protocol({"serial": serials[0]} if serials else {}, list(groups.values()))
