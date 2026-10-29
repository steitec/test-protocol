"""Combine the protocols of several input files for one device."""

from __future__ import annotations

from .model import InputError, Protocol


def merge(protocols: list[Protocol], header: dict[str, str]) -> Protocol:
    serials = [(p.inputs[0].name if p.inputs else "?", p.header["serial"])
               for p in protocols if p.header.get("serial")]
    given = header.get("serial")
    distinct = {sn for _, sn in serials} | ({given} if given else set())
    if len(distinct) > 1:
        listed = ", ".join(f"{name}={sn}" for name, sn in serials)
        if given:
            listed += f", --serial={given}"
        raise InputError(f"serial numbers differ: {listed}")
    merged = Protocol()
    for p in protocols:
        for key, value in p.header.items():
            if value and not merged.header.get(key):
                merged.header[key] = value
        merged.groups += p.groups
        merged.attachments += p.attachments
        merged.inputs += p.inputs
    merged.header.update({k: v for k, v in header.items() if v})
    return merged
