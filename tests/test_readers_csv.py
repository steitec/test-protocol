from pathlib import Path

import pytest

from test_protocol.model import InputError
from test_protocol.readers import csvfile

FIXTURES = Path(__file__).parent / "fixtures"


def test_bench_csv():
    text = (FIXTURES / "bench.csv").read_text(encoding="utf-8")
    assert csvfile.matches(text)
    p = csvfile.read(text, "measurements.csv")
    assert p.header == {"serial": "EPC-24-00137"}
    assert [g.name for g in p.groups][:3] == ["Power on", "Supply rails", "Boot"]
    rail = next(i for i in p.groups[1].items if i.name == "5V0")
    assert (rail.low, rail.high, rail.unit, rail.status) == (4.75, 5.25, "V", "PASS")
    assert p.verdict() == "PASS"


def test_german_excel_csv():
    text = "﻿Serial;Step;Measurement;Value;Unit;Low;High\nX1;Rails;5V0;5,014;V;4,75;5,25\n"
    assert csvfile.matches(text)
    p = csvfile.read(text, "excel.csv")
    item = p.groups[0].items[0]
    assert (item.value, item.low, item.high, item.status) == (5.014, 4.75, 5.25, "PASS")
    assert p.header == {"serial": "X1"}


def test_german_thousands_separator():
    p = csvfile.read("measurement;value\nflash;1.024,5\n", "x.csv")
    assert p.groups[0].items[0].value == 1024.5


def test_text_value():
    p = csvfile.read("measurement,value,result\nBIOS,5.27a,PASS\n", "x.csv")
    item = p.groups[0].items[0]
    assert (item.value, item.status) == ("5.27a", "PASS")


def test_missing_optional_columns():
    p = csvfile.read("Measurement,Value\ntemp,41.5\n", "plain.csv")
    assert [g.name for g in p.groups] == ["plain.csv"]
    item = p.groups[0].items[0]
    assert (item.value, item.status) == (41.5, "INFO")
    assert p.header == {}


def test_limits_evaluated_without_result():
    p = csvfile.read("measurement,value,low,high\nv,6,1,5\n", "x.csv")
    assert p.groups[0].items[0].status == "FAIL"


def test_given_result_kept():
    p = csvfile.read("measurement,value,low,high,result\nv,6,1,5,pass\n", "x.csv")
    assert p.groups[0].items[0].status == "PASS"


def test_two_serials_error():
    with pytest.raises(InputError, match="several serial numbers"):
        csvfile.read("serial,measurement,value\nA,v,1\nB,v,2\n", "x.csv")


def test_bad_result_value_error():
    with pytest.raises(InputError, match="line 3"):
        csvfile.read("measurement,value,result\nv,1,PASS\nw,2,MAYBE\n", "x.csv")


def test_not_csv():
    assert not csvfile.matches("name,score\na,1\n")
    assert not csvfile.matches("")
