"""The example units in examples/ must tell one consistent story per board."""

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).parent.parent / "examples"
UNITS = ["EPC-24-00137", "EPC-24-00142"]


def bench(unit: str) -> dict:
    return json.loads((EXAMPLES / unit / "bench-result.json").read_text())


def boot_suite(unit: str) -> ET.Element:
    return ET.parse(EXAMPLES / unit / "boot-log.xml").getroot()


def post_ram_mb(log: str) -> int:
    return int(re.search(r"POST: Memory (\d+) MB", log).group(1))


@pytest.mark.parametrize("unit", UNITS)
def test_boot_log_is_from_this_unit(unit):
    props = {p.get("name"): p.get("value") for p in boot_suite(unit).iter("property")}
    assert Path(props["dut"]).stem == unit
    dut_log = (EXAMPLES / props["dut"]).read_text()
    # same board as the bench run: the BIOS lines of the console capture
    assert dut_log.splitlines()[0] in bench(unit)["console_log"]


@pytest.mark.parametrize("unit", UNITS)
def test_ram_agrees_between_bench_and_boot_log(unit):
    data = bench(unit)
    props = {p.get("name"): p.get("value") for p in boot_suite(unit).iter("property")}
    post_in_bench = post_ram_mb(data["console_log"])
    post_in_boot_log = post_ram_mb((EXAMPLES / props["dut"]).read_text())
    assert post_in_bench == post_in_boot_log
    memory = next(s for s in data["steps"] if s["name"] == "Memory")
    ram_fact = next(c for c in boot_suite(unit).iter("testcase") if c.get("name") == "ram")
    ram_failed_in_boot_log = ram_fact.find("failure") is not None
    assert (memory["status"] == "FAIL") == ram_failed_in_boot_log
