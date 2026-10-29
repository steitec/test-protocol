"""JUnit XML (pytest --junitxml, boot-log-diff --junit, most CI tools)."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from ..model import Attachment, Group, Item, Protocol

_OUTCOMES = (("failure", "FAIL"), ("error", "ERROR"), ("skipped", "SKIP"))


def matches(root: ET.Element) -> bool:
    return root.tag in ("testsuites", "testsuite")


def _first_line(text: str | None) -> str:
    return (text or "").strip().split("\n", 1)[0].strip()


def read(root: ET.Element, name: str) -> Protocol:
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    groups: dict[str, Group] = {}
    details: list[str] = []
    for suite in suites:
        for case in suite.findall("testcase"):
            key = case.get("classname") or suite.get("name") or name
            group = groups.setdefault(key, Group(key, source=name))
            item = Item(case.get("name", ""), status="PASS")
            for tag, status in _OUTCOMES:
                outcome = case.find(tag)
                if outcome is not None:
                    item.status = status
                    item.message = _first_line(outcome.get("message")) or _first_line(outcome.text)
                    if status != "SKIP":
                        details.append(f"== {key} :: {item.name} ==\n{(outcome.text or '').strip()}")
                    break
            group.items.append(item)
    header = {}
    for prop in root.iter("property"):
        if prop.get("name") in ("serial", "serial_number") and prop.get("value"):
            header["serial"] = prop.get("value", "")
            break
    attachments = [Attachment(f"{name}: failure details", "\n\n".join(details))] if details else []
    return Protocol(header, list(groups.values()), attachments)
