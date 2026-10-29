"""interface-test-kit result.json."""

from __future__ import annotations

from ..model import Group, Item, Protocol


def matches(data: object) -> bool:
    return isinstance(data, dict) and {"profile", "mode", "steps"} <= data.keys()


def _group(step: dict, name: str) -> Group:
    attempts = step.get("attempts") or []
    last = attempts[-1] if attempts else {}
    items = []
    for m in last.get("measurements", []):
        item = Item(m["name"], value=m.get("value"), unit=m.get("unit") or "",
                    low=m.get("low"), high=m.get("high"))
        if m.get("passed") is not None:
            item.status = "PASS" if m["passed"] else "FAIL"
        items.append(item)
    message = step.get("message") or ""
    if step.get("passed_after_retry"):
        message += f" (passed after retry, {len(attempts)} attempts)"
    if step.get("equipment_id"):
        message += f" [equipment {step['equipment_id']}]"
    return Group(step["name"], items, status=step.get("status"), message=message.strip(),
                 source=name)


def read(data: dict, name: str) -> Protocol:
    profile = data.get("profile") or {}
    header = {
        "serial": data.get("serial_number"),
        "rma": data.get("rma"),
        "profile": f"{profile['name']} v{profile['version']}" if profile.get("name") else None,
        "station": data.get("station"),
        "operator": data.get("operator"),
        "started": data.get("started"),
        "finished": data.get("finished"),
        "mode": "selftest" if data.get("mode") == "selftest" else None,
    }
    return Protocol({k: str(v) for k, v in header.items() if v},
                    [_group(step, name) for step in data["steps"]])
