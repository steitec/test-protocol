import json
import subprocess
import sys
from pathlib import Path

import pytest

from test_protocol.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def f(name: str) -> str:
    return str(FIXTURES / name)


def test_summary_stdout_fail_exit_1(capsys):
    assert main([f("bench_fail.json")]) == 1
    out = capsys.readouterr().out
    assert out.splitlines()[0] == "EPC-24-00137: FAIL"
    assert "PASS 18" in out and "FAIL 2" in out
    assert "  FAIL  Storage / Reallocated sectors: 312 (≤ 10)" in out


def test_pass_exit_0(capsys):
    assert main([f("bench_pass.json")]) == 0
    assert capsys.readouterr().out.startswith("EPC-24-00137: PASS")


def test_writes_html_json(tmp_path, capsys):
    html, js = tmp_path / "p.html", tmp_path / "p.json"
    assert main([f("bench_fail.json"), "-o", str(html), "--json", str(js)]) == 1
    assert "EPC-24-00137" in html.read_text(encoding="utf-8")
    data = json.loads(js.read_text(encoding="utf-8"))
    assert data["format"] == "test-protocol/1"
    assert data["verdict"] == "FAIL"
    out = capsys.readouterr().out
    assert str(html) in out and str(js) in out


def test_meta_and_overrides(tmp_path):
    js = tmp_path / "p.json"
    main([f("pytest.xml"), "--serial", "SN-7", "--product", "EPC-24", "--operator", "jdoe",
          "--station", "S1", "--meta", "order=4711", "--meta", "customer=ACME = Ltd",
          "--json", str(js)])
    header = json.loads(js.read_text())["header"]
    assert header == {"serial": "SN-7", "product": "EPC-24", "station": "S1",
                      "operator": "jdoe", "order": "4711", "customer": "ACME = Ltd"}


@pytest.mark.parametrize("meta", ["order", "=4711"])
def test_bad_meta_exit_2(meta, capsys):
    assert main([f("bench_pass.json"), "--meta", meta]) == 2
    assert capsys.readouterr().err.startswith("test-protocol: error: --meta")


def test_no_results_exit_2(tmp_path, capsys):
    empty = tmp_path / "empty.csv"
    empty.write_text("serial,measurement,value\n")
    assert main([str(empty)]) == 2
    assert "no test results in the input" in capsys.readouterr().err


def test_no_serial_exit_2(capsys):
    assert main([f("pytest.xml")]) == 2
    assert "no serial number found; use --serial" in capsys.readouterr().err


def test_serial_conflict_exit_2(capsys):
    assert main([f("bench_pass.json"), f("itk_rma.json")]) == 2
    assert "serial numbers differ" in capsys.readouterr().err


def test_missing_input_exit_2(tmp_path, capsys):
    assert main([str(tmp_path / "nope.json")]) == 2
    assert "nope.json" in capsys.readouterr().err


def test_logo_embedded(tmp_path):
    logo, html = tmp_path / "logo.svg", tmp_path / "p.html"
    logo.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    main([f("bench_pass.json"), "--logo", str(logo), "--company", "ACME", "-o", str(html)])
    assert 'src="data:image/svg+xml;base64,' in html.read_text(encoding="utf-8")


def test_bad_logo_type_exit_2(tmp_path, capsys):
    logo = tmp_path / "logo.bmp"
    logo.write_bytes(b"BM")
    assert main([f("bench_pass.json"), "--logo", str(logo)]) == 2
    assert "logo" in capsys.readouterr().err


def test_limits_warning_and_input(tmp_path, capsys):
    limits, js = tmp_path / "limits.toml", tmp_path / "p.json"
    limits.write_text('[[limit]]\nmeasurement = "5V0"\nhigh = 4.0\n\n'
                      '[[limit]]\nmeasurement = "12V0"\nlow = 11\n')
    assert main([f("bench_pass.json"), "--limits", str(limits), "--json", str(js)]) == 1
    err = capsys.readouterr().err
    assert "test-protocol: warning: limit '12V0' matched no measurement" in err
    inputs = json.loads(js.read_text())["inputs"]
    assert [(i["name"], i["format"]) for i in inputs] == [
        ("bench_pass.json", "bench"), ("limits.toml", "limits")]


def test_require_limits(capsys):
    assert main([f("bench_pass.json")]) == 0
    assert main([f("bench_pass.json"), "--require-limits"]) == 1
    assert "no limit defined" in capsys.readouterr().out


def test_lang_and_title(tmp_path):
    html = tmp_path / "p.html"
    main([f("bench_pass.json"), "--lang", "de", "--title", "Endprüfung", "--approver",
          "-o", str(html)])
    text = html.read_text(encoding="utf-8")
    assert "Endprüfung" in text and "Freigegeben von" in text


def test_forced_format(tmp_path):
    data = tmp_path / "data.txt"
    data.write_text((FIXTURES / "bench.csv").read_text(encoding="utf-8"), encoding="utf-8")
    assert main([str(data), "--format", "csv"]) == 0


def test_json_input_round_trip(tmp_path, capsys):
    js = tmp_path / "p.json"
    main([f("bench_fail.json"), "--json", str(js)])
    assert main([str(js)]) == 1
    assert "EPC-24-00137: FAIL" in capsys.readouterr().out


def test_pdf_error_exit_2(tmp_path, monkeypatch, capsys):
    from test_protocol import pdf
    def fail(*args, **kwargs):
        raise pdf.PdfError("no PDF engine: test")
    monkeypatch.setattr("test_protocol.cli.write_pdf", fail)
    assert main([f("bench_pass.json"), "--pdf", str(tmp_path / "x.pdf")]) == 2
    assert "no PDF engine" in capsys.readouterr().err


def test_module_entry():
    result = subprocess.run([sys.executable, "-m", "test_protocol", "--version"],
                            capture_output=True, text=True)
    assert result.stdout.strip() == "test-protocol 0.1.0"
