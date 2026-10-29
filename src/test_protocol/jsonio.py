"""The tool's own JSON format: a stable interface for other tools."""

from __future__ import annotations

from dataclasses import asdict, fields

from .model import Attachment, Group, InputFile, Item, Protocol

FORMAT_ID = "test-protocol/1"


def matches(data: object) -> bool:
    return isinstance(data, dict) and data.get("format") == FORMAT_ID


def to_dict(p: Protocol) -> dict:
    return {"format": FORMAT_ID, "verdict": p.verdict(), "counts": p.counts(), **asdict(p)}


def _make(cls, d: dict):
    return cls(**{f.name: d[f.name] for f in fields(cls) if f.name in d})


def from_dict(d: dict, name: str) -> Protocol:
    groups = []
    for g in d.get("groups", []):
        group = _make(Group, g)
        group.items = [_make(Item, i) for i in g.get("items", [])]
        group.source = group.source or name
        groups.append(group)
    return Protocol(dict(d.get("header", {})), groups,
                    [_make(Attachment, a) for a in d.get("attachments", [])],
                    [_make(InputFile, i) for i in d.get("inputs", [])])
