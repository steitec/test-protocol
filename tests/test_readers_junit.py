import xml.etree.ElementTree as ET
from pathlib import Path

from test_protocol.readers import junit

FIXTURES = Path(__file__).parent / "fixtures"


def read(name: str):
    return junit.read(ET.parse(FIXTURES / name).getroot(), name)


def test_boot_log_diff_junit():
    p = read("boot-log-diff.xml")
    assert [g.name for g in p.groups] == [
        "boot-log-diff.facts", "boot-log-diff.lines", "boot-log-diff.faults"]
    dram = next(i for i in p.groups[0].items if i.name == "dram")
    assert (dram.status, dram.message, dram.value) == ("FAIL", "2 GiB -> 1 GiB", None)
    assert all(g.source == "boot-log-diff.xml" for g in p.groups)
    assert p.verdict() == "FAIL"


def test_pytest_junit():
    p = read("pytest.xml")
    assert [g.name for g in p.groups] == ["test_sample.TestPower", "test_sample"]
    counts = p.counts()
    assert (counts["PASS"], counts["FAIL"], counts["ERROR"], counts["SKIP"]) == (2, 1, 1, 1)
    inrush = p.groups[0].items[2]
    assert inrush.message == "AssertionError: inrush too high"
    can = p.groups[1].items[1]
    assert (can.name, can.status, can.message) == ("test_can", "SKIP", "no CAN adapter")


def test_group_falls_back_to_suite_name():
    root = ET.fromstring('<testsuite name="eol"><testcase name="a"/></testsuite>')
    p = junit.read(root, "x.xml")
    assert [g.name for g in p.groups] == ["eol"]
    assert p.groups[0].items[0].status == "PASS"


def test_serial_property():
    root = ET.fromstring(
        '<testsuites><testsuite name="s"><properties>'
        '<property name="serial_number" value="SN-9"/></properties>'
        '<testcase classname="c" name="a"/></testsuite></testsuites>')
    assert junit.read(root, "x.xml").header == {"serial": "SN-9"}
    assert read("pytest.xml").header == {}


def test_failure_attachment():
    p = read("pytest.xml")
    assert [a.title for a in p.attachments] == ["pytest.xml: failure details"]
    text = p.attachments[0].text
    assert "== test_sample.TestPower :: test_inrush ==" in text
    assert "== test_sample :: test_eeprom ==" in text
    assert "fixture exploded" in text


def test_matches():
    assert junit.matches(ET.fromstring("<testsuites/>"))
    assert junit.matches(ET.fromstring("<testsuite/>"))
    assert not junit.matches(ET.fromstring("<html/>"))
