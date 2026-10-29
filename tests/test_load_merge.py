import json
import shutil
from pathlib import Path

import pytest

from test_protocol.merge import merge
from test_protocol.model import InputError
from test_protocol.readers import load

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize("name,fmt", [
    ("bench_pass.json", "bench"), ("itk_rma.json", "itk"), ("pytest.xml", "junit"),
    ("bench.csv", "csv")])
def test_detect_each_fixture(name, fmt):
    p = load(FIXTURES / name)
    assert [(i.name, i.format) for i in p.inputs] == [(name, fmt)]
    assert len(p.inputs[0].sha256) == 64
    assert p.groups


def test_detect_without_extension(tmp_path):
    for name, fmt in (("bench_pass.json", "bench"), ("pytest.xml", "junit"), ("bench.csv", "csv")):
        target = tmp_path / name.split(".")[0]
        shutil.copy(FIXTURES / name, target)
        assert load(target).inputs[0].format == fmt


def test_own_json_detected(tmp_path):
    from test_protocol import jsonio
    target = tmp_path / "p.json"
    target.write_text(json.dumps(jsonio.to_dict(load(FIXTURES / "bench_fail.json"))))
    p = load(target)
    assert p.inputs[-1].format == "json"
    assert p.verdict() == "FAIL"


def test_forced_format(tmp_path):
    target = tmp_path / "data.txt"
    shutil.copy(FIXTURES / "bench.csv", target)
    assert load(target, "csv").inputs[0].format == "csv"
    with pytest.raises(InputError, match="data.txt"):
        load(target, "junit")


def test_unknown_format_error(tmp_path):
    target = tmp_path / "notes.txt"
    target.write_text("hello\n")
    with pytest.raises(InputError, match="notes.txt: unknown input format; use --format"):
        load(target)


def test_invalid_json_error_names_file(tmp_path):
    target = tmp_path / "broken.json"
    target.write_text("{not json")
    with pytest.raises(InputError, match="broken.json"):
        load(target)


def test_json_of_unknown_shape(tmp_path):
    target = tmp_path / "other.json"
    target.write_text('{"a": 1}')
    with pytest.raises(InputError, match="unknown input format"):
        load(target)


def test_missing_file(tmp_path):
    with pytest.raises(InputError, match="nope.csv"):
        load(tmp_path / "nope.csv")


def with_serial(tmp_path, serial):
    data = json.loads((FIXTURES / "itk_rma.json").read_text())
    data["serial_number"] = serial
    target = tmp_path / "itk.json"
    target.write_text(json.dumps(data))
    return load(target)


def test_merge_bench_itk_junit_same_serial(tmp_path):
    parts = [load(FIXTURES / "bench_pass.json"), with_serial(tmp_path, "EPC-24-00137"),
             load(FIXTURES / "boot-log-diff.xml")]
    p = merge(parts, {})
    assert p.header["serial"] == "EPC-24-00137"
    assert p.header["station"] == "EOL-01"          # first input wins
    assert p.header["rma"] == "RMA-2026-0042"       # filled from a later input
    assert [i.name for i in p.inputs] == ["bench_pass.json", "itk.json", "boot-log-diff.xml"]
    assert len(p.groups) == sum(len(x.groups) for x in parts)
    assert p.verdict() == "FAIL"


def test_merge_serial_conflict(tmp_path):
    parts = [load(FIXTURES / "bench_pass.json"), with_serial(tmp_path, "EPC-24-99999")]
    with pytest.raises(InputError, match="serial numbers differ: bench_pass.json=EPC-24-00137"):
        merge(parts, {})


def test_command_line_serial_must_match_inputs():
    with pytest.raises(InputError, match="serial numbers differ"):
        merge([load(FIXTURES / "bench_pass.json")], {"serial": "OTHER"})


def test_cli_header_overrides():
    p = merge([load(FIXTURES / "pytest.xml")], {"serial": "SN-1", "station": "S2", "order": "4711"})
    assert p.header == {"serial": "SN-1", "station": "S2", "order": "4711"}
    p = merge([load(FIXTURES / "bench_pass.json")], {"station": "EOL-02"})
    assert p.header["station"] == "EOL-02"
