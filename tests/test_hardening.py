"""Regression tests from the final review: no PASS protocol for a unit that should not pass."""

import json
from pathlib import Path

import pytest

from test_protocol.cli import main
from test_protocol.i18n import fmt_number
from test_protocol.limits import load_limits
from test_protocol.model import InputError, Item
from test_protocol.readers import load

FIXTURES = Path(__file__).parent / "fixtures"


def write(tmp_path, name: str, content) -> Path:
    path = tmp_path / name
    if isinstance(content, (dict, list)):
        content = json.dumps(content)
    path.write_text(content, encoding="utf-8")
    return path


def bench(measurements, status="PASS", serial="SN1"):
    return {"station": "S", "serial_number": serial, "console_log": "", "status": status,
            "steps": [{"name": "Rails", "status": "PASS", "message": "",
                       "measurements": measurements}]}


# C-1: limits without a given status are evaluated
def test_bench_measurement_without_passed_is_evaluated(tmp_path):
    p = load(write(tmp_path, "b.json", bench([{"name": "5V0", "value": 7.0, "low": 4.9, "high": 5.1}])))
    assert p.items()[0].status == "FAIL"
    assert p.verdict() == "FAIL"


def test_nan_value_without_status_fails(tmp_path):
    p = load(write(tmp_path, "b.json", '{"station": "S", "serial_number": "SN1", "console_log": "",'
                   ' "steps": [{"name": "R", "status": "PASS", "measurements":'
                   ' [{"name": "v", "value": NaN, "low": 1, "high": 2}]}]}'))
    assert (p.items()[0].status, p.items()[0].message) == ("FAIL", "value is not a number")


def test_own_json_item_without_status_is_evaluated(tmp_path):
    data = {"format": "test-protocol/1", "header": {"serial": "SN1"},
            "groups": [{"name": "g", "items": [{"name": "v", "value": 5, "low": 1, "high": 2}]}]}
    assert load(write(tmp_path, "p.json", data)).verdict() == "FAIL"


# C-2: the run verdict of the input tool counts
def test_aborted_itk_run_is_not_pass(tmp_path):
    data = json.loads((FIXTURES / "itk_rma.json").read_text())
    data["steps"] = [s for s in data["steps"] if s["status"] == "PASS"]
    data["status"] = "ABORTED"
    data["only"] = ["usb", "lan1"]
    p = load(write(tmp_path, "itk.json", data))
    assert p.verdict() == "FAIL"
    run = p.groups[-1]
    assert (run.status, run.message) == ("ERROR", "run aborted before all steps were done")
    assert p.header["only"] == "usb, lan1"


def test_bench_run_fail_with_passing_steps_is_fail(tmp_path):
    p = load(write(tmp_path, "b.json", bench([{"name": "v", "value": 1, "passed": True}], status="FAIL")))
    assert p.verdict() == "FAIL"


# I-3: a given PASS that contradicts the limits
def test_csv_pass_contradicting_limits(tmp_path):
    p = load(write(tmp_path, "m.csv", "measurement,value,low,high,result\n5V0,7.0,4.9,5.1,PASS\n"))
    item = p.items()[0]
    assert (item.status, item.message) == ("FAIL", "result PASS contradicts the limits")


# I-4: statuses in own JSON are validated
def test_own_json_status_lowercase_and_unknown(tmp_path):
    data = {"format": "test-protocol/1", "header": {"serial": "SN1"},
            "groups": [{"name": "g", "status": "fail", "items": [{"name": "a", "status": "pass"}]}]}
    assert load(write(tmp_path, "p.json", data)).verdict() == "FAIL"
    data["groups"][0]["status"] = "ABORTED"
    with pytest.raises(InputError, match="p.json: unknown status 'ABORTED'"):
        load(write(tmp_path, "p.json", data))


# I-5: malformed inputs are input errors (exit 2), not tracebacks
@pytest.mark.parametrize("data", [
    bench([{"value": 1}]),
    {"format": "test-protocol/1", "header": {"serial": "S"}, "groups": [{"name": "g", "items": [{"value": 1}]}]},
    {"format": "test-protocol/1", "header": {"serial": "S"},
     "groups": [{"name": "g", "items": [{"name": "a", "value": 1, "low": "x"}]}]},
    {"format": "test-protocol/1", "header": "S", "groups": []},
    {"station": "S", "serial_number": "S", "console_log": "", "steps": {"a": 1}},
])
def test_malformed_json_exit_2(tmp_path, capsys, data):
    assert main([str(write(tmp_path, "bad.json", data))]) == 2
    assert capsys.readouterr().err.startswith("test-protocol: error: bad.json:")


# I-6: limits that would switch checking off
@pytest.mark.parametrize("body,match", [
    ('measurement = "a"\nunit = "V"', "needs low, high or expect"),
    ('measurement = "a"\nlow = nan', "low must be a finite number"),
    ('measurement = "a"\nhigh = inf', "high must be a finite number"),
])
def test_limits_that_disable_checks(tmp_path, body, match):
    with pytest.raises(InputError, match=match):
        load_limits(write(tmp_path, "limits.toml", "[[limit]]\n" + body + "\n"))


# I-7: text checks on CSV values
def test_csv_text_check_keeps_cell_text(tmp_path):
    p = load(write(tmp_path, "m.csv", "measurement,value,low,result\nBIOS,5.10a,5.10a,\n"))
    assert (p.items()[0].value, p.items()[0].status) == ("5.10a", "PASS")


def test_expect_limit_on_numeric_csv_value(tmp_path):
    from test_protocol.limits import Limit, apply_limits
    p = load(write(tmp_path, "m.csv", "serial,measurement,value\nSN1,BIOS,5.10\nSN1,ports,2\n"))
    apply_limits(p, [Limit("BIOS", expect="5.10"), Limit("ports", expect="2")], "l.toml")
    assert [i.status for i in p.items()] == ["PASS", "PASS"]


def test_expect_against_number_compares_numbers():
    item = Item("count", value=2.0, expect="2")
    item.evaluate()
    assert item.status == "PASS"


# I-8: values are shown exactly
def test_fmt_number_exact():
    assert fmt_number(5.1000001, "en") == "5.1000001"
    assert fmt_number(12345678.0, "en") == "12345678"
    assert fmt_number(2.0, "de") == "2"
    assert fmt_number(4.9918, "de") == "4,9918"


# I-9: nothing evaluated is not a PASS
def test_only_info_values_exit_2(tmp_path, capsys):
    path = write(tmp_path, "m.csv", "serial,measurement,value\nSN1,temp,41.5\nSN1,fan,1200\n")
    assert main([str(path)]) == 2
    assert "no evaluated checks" in capsys.readouterr().err
    assert main([str(path), "--require-limits"]) == 1


def test_info_values_are_called_out_in_html(tmp_path):
    path = write(tmp_path, "m.csv", "serial,measurement,value,high\nSN1,temp,41.5,80\nSN1,fan,1200,\n")
    html = tmp_path / "p.html"
    assert main([str(path), "-o", str(html)]) == 0
    assert "1 value without limits — not evaluated" in html.read_text(encoding="utf-8")


# I-10: every input must contain results
def test_empty_input_next_to_others(tmp_path, capsys):
    empty = write(tmp_path, "boot.xml", "<testsuites/>")
    assert main([str(FIXTURES / "bench_pass.json"), str(empty)]) == 2
    assert "boot.xml: no test results" in capsys.readouterr().err


# I-11: German Excel's default CSV export is Windows-1252
def test_cp1252_csv(tmp_path):
    path = tmp_path / "excel.csv"
    path.write_bytes("Serial;Measurement;Value;Unit;High\nSN1;CPU;46,5;°C;80\n".encode("cp1252"))
    p = load(path)
    assert p.items()[0].unit == "°C"
    assert p.inputs[0].format == "csv (cp1252)"
