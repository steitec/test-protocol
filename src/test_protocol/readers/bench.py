"""bench-automation result.json."""

from __future__ import annotations

from ..model import Attachment, Group, Item, Protocol, run_group


def matches(data: object) -> bool:
    return isinstance(data, dict) and {"steps", "station", "console_log"} <= data.keys()


def _item(m: dict) -> Item:
    item = Item(m["name"], value=m.get("value"), unit=m.get("unit") or "")
    low, high = m.get("low"), m.get("high")
    if isinstance(low, str):        # bench writes text checks as low = expected text
        item.expect = low
    else:
        item.low, item.high = low, high
    passed = m.get("passed")
    if passed is not None:
        item.status = "PASS" if passed else "FAIL"
    return item


def read(data: dict, name: str) -> Protocol:
    header = {"serial": str(data.get("serial_number") or ""), "station": data.get("station") or "",
              "started": data.get("started") or ""}
    groups = [Group(step["name"], [_item(m) for m in step.get("measurements", [])],
                    status=step.get("status"), message=step.get("message") or "", source=name)
              for step in data["steps"]]
    run = run_group(data.get("status"), groups, name)
    if run:
        groups.append(run)
    attachments = []
    if data.get("console_log"):
        attachments.append(Attachment("Console log", data["console_log"]))
    if data.get("instruments"):
        attachments.append(Attachment(
            "Instruments", "\n".join(f"{k}: {v}" for k, v in data["instruments"].items())))
    return Protocol({k: v for k, v in header.items() if v}, groups, attachments)
