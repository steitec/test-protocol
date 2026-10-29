import json
from pathlib import Path

import pytest

from test_protocol import jsonio
from test_protocol.readers import bench, itk

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def find(p, group: str, item: str | None = None):
    g = next(g for g in p.groups if g.name == group)
    return g if item is None else next(i for i in g.items if i.name == item)


def test_bench_pass():
    p = bench.read(load("bench_pass.json"), "result.json")
    assert p.header["serial"] == "EPC-24-00137"
    assert p.header["station"] == "EOL-01"
    assert p.header["started"].startswith("2026-10-29T18:04:00")
    assert p.verdict() == "PASS"
    rail = find(p, "Supply rails", "5V0")
    assert (rail.low, rail.high, rail.unit, rail.status) == (4.75, 5.25, "V", "PASS")
    assert all(g.source == "result.json" for g in p.groups)
    assert [a.title for a in p.attachments] == ["Console log", "Instruments"]
    assert "psu: scpi-sim,PSU" in p.attachments[1].text
    assert p.inputs == []


def test_bench_fail():
    p = bench.read(load("bench_fail.json"), "result.json")
    assert p.verdict() == "FAIL"
    failed = [(g.name, i.name if i else None) for g, i in p.failures()]
    assert failed == [("Storage", "Reallocated sectors"), ("Storage", "Pending sectors")]
    assert find(p, "Storage").message == "Reallocated sectors, Pending sectors out of limits"


def test_bench_text_limit():
    p = bench.read(load("bench_fail.json"), "result.json")
    bios = find(p, "Identity", "BIOS version")
    assert (bios.expect, bios.low, bios.high, bios.status) == ("5.27", None, None, "PASS")


def test_itk():
    p = itk.read(load("itk_rma.json"), "itk.json")
    assert p.header["serial"] == "EPC-24-00211"
    assert p.header["rma"] == "RMA-2026-0042"
    assert p.header["profile"] == "EPC-24 variant B v3"
    assert p.header["operator"] == "jdoe"
    assert p.header["finished"].startswith("2026-10-28T09:16:40")
    assert "mode" not in p.header
    lan = find(p, "LAN1")
    assert lan.message == ("link 1000 Mbit/s full duplex (passed after retry, 3 attempts)"
                           " [equipment CBL-07]")
    assert [i.name for i in lan.items] == ["link speed"]
    assert find(p, "USB", "write speed").low == 10
    assert p.counts()["FAIL"] == 1
    assert p.verdict() == "FAIL"


def test_itk_selftest_mode():
    data = load("itk_rma.json") | {"mode": "selftest"}
    assert itk.read(data, "itk.json").header["mode"] == "selftest"


@pytest.mark.parametrize("name,expected", [
    ("bench_pass.json", "bench"), ("bench_fail.json", "bench"), ("itk_rma.json", "itk")])
def test_matches_disjoint(name, expected):
    data = load(name)
    hits = [n for n, mod in (("bench", bench), ("itk", itk), ("json", jsonio)) if mod.matches(data)]
    assert hits == [expected]


def test_json_round_trip():
    p = bench.read(load("bench_fail.json"), "result.json")
    d = jsonio.to_dict(p)
    assert next(iter(d)) == "format"
    assert d["format"] == "test-protocol/1"
    assert d["verdict"] == "FAIL"
    assert jsonio.matches(d)
    again = jsonio.from_dict(json.loads(json.dumps(d)), "x.json")
    assert jsonio.to_dict(again) == d
