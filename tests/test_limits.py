from pathlib import Path

import pytest

from test_protocol.limits import Limit, apply_limits, load_limits, require_limits
from test_protocol.model import Group, InputError, Item, Protocol
from test_protocol.readers import load

FIXTURES = Path(__file__).parent / "fixtures"


def write(tmp_path, text: str) -> Path:
    path = tmp_path / "limits.toml"
    path.write_text(text, encoding="utf-8")
    return path


def rail(p: Protocol, name: str) -> Item:
    return next(i for g in p.groups if g.name == "Supply rails" for i in g.items if i.name == name)


def test_load(tmp_path):
    limits = load_limits(write(tmp_path, """
[[limit]]
step = "Supply rails"
measurement = "5V0"
low = 4.95
high = 5
unit = "V"

[[limit]]
measurement = "BIOS version"
expect = "5.27"
"""))
    assert limits == [Limit("5V0", "Supply rails", 4.95, 5.0, None, "V"),
                      Limit("BIOS version", expect="5.27")]


def test_override_and_reevaluate():
    p = load(FIXTURES / "bench_pass.json")
    unmatched = apply_limits(p, [Limit("5v0", "supply RAILS", 4.95, 5.0)], "limits.toml")
    assert unmatched == []
    item = rail(p, "5V0")
    assert (item.low, item.high, item.limit_source) == (4.95, 5.0, "limits.toml")
    assert item.status == ("PASS" if 4.95 <= item.value <= 5.0 else "FAIL")
    tight = Limit("5V0", low=4.0, high=4.5)
    apply_limits(p, [tight], "limits.toml")
    assert rail(p, "5V0").status == "FAIL"
    assert p.verdict() == "FAIL"


def test_step_specific_wins():
    p = load(FIXTURES / "bench_pass.json")
    apply_limits(p, [Limit("3V3", "Supply rails", 3.0, 3.6), Limit("3V3", None, 0, 1)], "l.toml")
    assert (rail(p, "3V3").low, rail(p, "3V3").status) == (3.0, "PASS")


def test_expect_limit_replaces_numeric():
    item = Item("fw", value="1.2", low=1.0, high=2.0, status="PASS")
    p = Protocol(groups=[Group("g", [item])])
    apply_limits(p, [Limit("fw", expect="1.3")], "l.toml")
    assert (item.low, item.high, item.expect, item.status) == (None, None, "1.3", "FAIL")


def test_unmatched_returned():
    p = load(FIXTURES / "bench_pass.json")
    missing = Limit("12V0", low=11.0)
    assert apply_limits(p, [missing, Limit("5V0", low=4.0)], "l.toml") == [missing]


@pytest.mark.parametrize("body,match", [
    ('measurement = "a"\nlow = 2\nhigh = 1', "low > high"),
    ('measurement = "a"\nlimit = 1', "unknown key 'limit'"),
    ('low = 1', "missing 'measurement'"),
    ('measurement = "a"\nexpect = "x"\nlow = 1', "expect"),
    ('measurement = "a"\nlow = "one"', "low must be a finite number"),
])
def test_bad_files(tmp_path, body, match):
    with pytest.raises(InputError, match=f"limits.toml: limit 1: .*{match}"):
        load_limits(write(tmp_path, "[[limit]]\n" + body + "\n"))


def test_invalid_toml(tmp_path):
    with pytest.raises(InputError, match="limits.toml"):
        load_limits(write(tmp_path, "[[limit]\n"))


def test_require_limits():
    p = Protocol(groups=[Group("g", [Item("a", "PASS", value=1.0), Item("b", "PASS"),
                                     Item("c", "PASS", value=2.0, high=3.0)])])
    require_limits(p)
    a, b, c = p.groups[0].items
    assert (a.status, a.message) == ("FAIL", "no limit defined")
    assert (b.status, c.status) == ("PASS", "PASS")


def test_items_without_value_ignored():
    p = load(FIXTURES / "boot-log-diff.xml")
    assert apply_limits(p, [Limit("dram", low=1.0)], "l.toml") == [Limit("dram", low=1.0)]
