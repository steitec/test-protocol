import math

import pytest

from test_protocol.model import Group, Item, Protocol


def evaluated(**kwargs) -> Item:
    item = Item("m", **kwargs)
    item.evaluate()
    return item


def test_numeric_limits():
    assert evaluated(value=5.01, low=4.75, high=5.25).status == "PASS"
    assert evaluated(value=5.3, low=4.75, high=5.25).status == "FAIL"
    assert evaluated(value=2.8, high=2.8).status == "PASS"
    assert evaluated(value=4.75, low=4.75).status == "PASS"
    assert evaluated(value=4.7, low=4.75).status == "FAIL"


def test_exact_value():
    assert evaluated(value=3.0, low=3.0, high=3.0).status == "PASS"
    assert evaluated(value=3.01, low=3.0, high=3.0).status == "FAIL"


def test_string_number_value():
    assert evaluated(value="5.01", low=4.75, high=5.25).status == "PASS"


@pytest.mark.parametrize("value", ["n/a", float("nan"), math.inf, None, True])
def test_non_numeric_value_fails(value):
    item = evaluated(value=value, low=1.0, high=2.0)
    assert item.status == "FAIL"
    assert item.message == "value is not a number"


def test_expect_text():
    assert evaluated(value=" 5.27", expect="5.27").status == "PASS"
    assert evaluated(value="5.28", expect="5.27").status == "FAIL"


def test_limits_override_given_status():
    assert evaluated(value=9.0, high=5.0, status="PASS").status == "FAIL"


def test_no_limits_keeps_status_or_info():
    assert evaluated(value=1.0, status="PASS").status == "PASS"
    assert evaluated(value=1.0).status == "INFO"
    assert not Item("m", value=1.0).has_limits()
    assert Item("m", value=1.0, expect="x").has_limits()


def protocol(*groups: Group) -> Protocol:
    return Protocol(header={"serial": "SN1"}, groups=list(groups))


def test_verdict():
    ok = protocol(Group("g", [Item("a", "PASS"), Item("b", "SKIP"), Item("c", "INFO")]))
    assert ok.verdict() == "PASS"
    assert protocol(Group("g", [Item("a", "PASS"), Item("b", "ERROR")])).verdict() == "FAIL"
    assert protocol(Group("g", [Item("a", "FAIL")])).verdict() == "FAIL"
    assert protocol(Group("boot", status="ERROR")).verdict() == "FAIL"


def test_failing_group_status_with_passing_items_fails():
    assert protocol(Group("g", [Item("a", "PASS")], status="FAIL")).verdict() == "FAIL"


def test_counts_and_failures():
    g1 = Group("g1", [Item("a", "PASS"), Item("b", "FAIL"), Item("c", "SKIP")])
    g2 = Group("boot", status="ERROR", message="timeout")
    g3 = Group("g3", [Item("d", "ERROR")])
    p = protocol(g1, g2, g3)
    assert p.counts() == {"PASS": 1, "FAIL": 1, "ERROR": 2, "SKIP": 1, "INFO": 0}
    assert [(g.name, i.name if i else None) for g, i in p.failures()] == [
        ("g1", "b"), ("boot", None), ("g3", "d")]
    assert [i.name for i in p.items()] == ["a", "b", "c", "d"]


def test_failing_group_with_passing_items_is_counted():
    p = protocol(Group("g", [Item("a", "PASS")], status="FAIL", message="checksum"))
    assert p.counts()["FAIL"] == 1
    assert [(g.name, i) for g, i in p.failures()] == [("g", None)]
