"""Read one input file into a Protocol, detecting its format."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

from .. import jsonio
from ..model import STATUSES, InputError, InputFile, Item, Protocol
from . import bench, csvfile, itk, junit

FORMATS = ("auto", "bench", "itk", "junit", "csv", "json")
_JSON_READERS = (("json", jsonio.matches, jsonio.from_dict), ("itk", itk.matches, itk.read),
                 ("bench", bench.matches, bench.read))


def _parse_json(text: str, name: str) -> object:
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise InputError(f"{name}: invalid JSON: {e}") from None


def _parse_xml(text: str, name: str) -> ET.Element:
    try:
        return ET.fromstring(text.encode("utf-8"))
    except ET.ParseError as e:
        raise InputError(f"{name}: invalid XML: {e}") from None


def _from_json(data: object, name: str, fmt: str) -> tuple[str, Protocol] | None:
    for key, test, read in _JSON_READERS:
        if fmt in ("auto", key) and test(data):
            return key, read(data, name)  # type: ignore[arg-type]
    return None


def _detect(text: str, name: str, suffix: str, fmt: str) -> tuple[str, Protocol] | None:
    if fmt in ("bench", "itk", "json") or (fmt == "auto" and suffix == ".json"):
        return _from_json(_parse_json(text, name), name, fmt)
    if fmt == "junit" or (fmt == "auto" and suffix == ".xml"):
        root = _parse_xml(text, name)
        return ("junit", junit.read(root, name)) if junit.matches(root) else None
    if fmt == "csv" or (fmt == "auto" and suffix == ".csv"):
        return ("csv", csvfile.read(text, name)) if csvfile.matches(text) else None
    # unknown extension: try each kind without failing on parse errors
    stripped = text.lstrip("﻿ \t\r\n")
    if stripped.startswith(("{", "[")):
        try:
            return _from_json(json.loads(text), name, "auto")
        except json.JSONDecodeError:
            return None
    if stripped.startswith("<"):
        try:
            root = ET.fromstring(text.encode("utf-8"))
        except ET.ParseError:
            return None
        return ("junit", junit.read(root, name)) if junit.matches(root) else None
    return ("csv", csvfile.read(text, name)) if csvfile.matches(text) else None


def _status(value: object, name: str) -> str | None:
    if value is None:
        return None
    status = str(value).strip().upper()
    if status not in STATUSES:
        raise InputError(f"{name}: unknown status {value!r}")
    return status


def _check_item(item: Item, name: str) -> None:
    if not isinstance(item.name, str) or not item.name:
        raise InputError(f"{name}: a measurement has no name")
    for bound in ("low", "high"):
        value = getattr(item, bound)
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                  or not math.isfinite(value)):
            raise InputError(f"{name}: {item.name}: {bound} must be a finite number")
    if item.expect is not None and not isinstance(item.expect, str):
        item.expect = str(item.expect)
    item.status = _status(item.status, name)
    if item.status is None:
        item.evaluate()
    elif item.status == "PASS" and item.has_limits():
        check = copy.copy(item)
        check.evaluate()
        if check.status == "FAIL":
            item.status = "FAIL"
            item.message = "result PASS contradicts the limits"


def _normalize(p: Protocol, name: str) -> None:
    """Checks every reader's output, so no input path can skip evaluation."""
    if not isinstance(p.header, dict):
        raise InputError(f"{name}: header must be an object")
    p.header = {str(k): str(v).strip() for k, v in p.header.items() if v not in (None, "")}
    for group in p.groups:
        if not isinstance(group.name, str) or not group.name:
            raise InputError(f"{name}: a step has no name")
        group.status = _status(group.status, name)
        for item in group.items:
            _check_item(item, name)
    if not p.items() and not any(g.status for g in p.groups):
        raise InputError(f"{name}: no test results in the input")


def _decode(raw: bytes, path: Path, fmt: str) -> tuple[str, str]:
    try:
        return raw.decode("utf-8-sig"), ""
    except UnicodeDecodeError:
        pass
    if fmt == "csv" or (fmt == "auto" and path.suffix.lower() == ".csv"):
        return raw.decode("cp1252", errors="replace"), " (cp1252)"   # German Excel default
    raise InputError(f"{path.name}: not UTF-8 text")


def load(path: Path, fmt: str = "auto") -> Protocol:
    path = Path(path)
    try:
        raw = path.read_bytes()
    except OSError as e:
        raise InputError(f"{path.name}: cannot read: {e.strerror or e}") from None
    text, encoding = _decode(raw, path, fmt)
    try:
        found = _detect(text, path.name, path.suffix.lower(), fmt)
    except (KeyError, TypeError, ValueError, AttributeError, IndexError) as e:
        raise InputError(f"{path.name}: malformed input ({type(e).__name__}: {e})") from None
    if found is None:
        hint = "use --format" if fmt == "auto" else f"not a {fmt} file"
        raise InputError(f"{path.name}: unknown input format; {hint}")
    kind, protocol = found
    _normalize(protocol, path.name)
    protocol.inputs.append(InputFile(path.name, hashlib.sha256(raw).hexdigest(), kind + encoding))
    return protocol
