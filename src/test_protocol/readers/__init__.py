"""Read one input file into a Protocol, detecting its format."""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from .. import jsonio
from ..model import InputError, InputFile, Protocol
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


def load(path: Path, fmt: str = "auto") -> Protocol:
    path = Path(path)
    try:
        raw = path.read_bytes()
    except OSError as e:
        raise InputError(f"{path.name}: cannot read: {e.strerror or e}") from None
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise InputError(f"{path.name}: not UTF-8 text") from None
    found = _detect(text, path.name, path.suffix.lower(), fmt)
    if found is None:
        hint = "use --format" if fmt == "auto" else f"not a {fmt} file"
        raise InputError(f"{path.name}: unknown input format; {hint}")
    kind, protocol = found
    protocol.inputs.append(InputFile(path.name, hashlib.sha256(raw).hexdigest(), kind))
    return protocol
