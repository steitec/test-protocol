import re
from datetime import datetime, timezone
from pathlib import Path

from test_protocol.html import RenderOptions, render_html
from test_protocol.i18n import TEXTS, fmt_number
from test_protocol.limits import Limit, apply_limits
from test_protocol.model import Attachment, Group, Item, Protocol
from test_protocol.readers import load

FIXTURES = Path(__file__).parent / "fixtures"
FIXED = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


def render(p: Protocol, **kwargs) -> str:
    return render_html(p, RenderOptions(tool_version="0.1.0", generated=FIXED, **kwargs))


def test_sections_present():
    out = render(load(FIXTURES / "bench_pass.json"))
    for section in ("header", "details", "summary", "results", "attachments",
                    "traceability", "signatures"):
        assert f'id="{section}"' in out
    assert out.startswith("<!doctype html>")
    assert "EPC-24-00137" in out
    assert '<html lang="en">' in out
    assert "Test protocol" in out


def test_verdict_badge_fail():
    out = render(load(FIXTURES / "bench_fail.json"))
    header = out.split('id="header"', 1)[1].split("</header>", 1)[0]
    assert 'class="verdict fail"' in header
    summary = out.split('id="summary"', 1)[1].split("</section>", 1)[0]
    assert "Reallocated sectors" in summary
    assert "Pending sectors" in summary


def test_pass_has_no_failure_table():
    out = render(load(FIXTURES / "bench_pass.json"))
    summary = out.split('id="summary"', 1)[1].split("</section>", 1)[0]
    assert 'class="verdict pass"' in out
    assert "<table" not in summary


def test_escaping():
    p = Protocol(header={"serial": 'SN"1', "note": '"x" & <y>'},
                 groups=[Group("<g>", [Item("<b>&", "FAIL", value="<v>", message="<m>")])],
                 attachments=[Attachment("<a>", "</pre><script>alert(1)</script>")])
    out = render(p, title="<script>", company="A&B")
    assert "<script>" not in out
    assert "<b>&" not in out and "<g>" not in out and "<v>" not in out and "<m>" not in out
    assert "&lt;b&gt;&amp;" in out
    assert "A&amp;B" in out
    assert "&quot;x&quot; &amp; &lt;y&gt;" in out
    assert 'content: "SN\\"1' in out or 'content: "SN\\22 1' in out


def test_german():
    out = render(load(FIXTURES / "bench_pass.json"), lang="de")
    assert '<html lang="de">' in out
    assert "Prüfprotokoll" in out
    assert "Seriennummer" in out
    assert re.search(r"\d,\d{2,4} V", out)          # decimal comma in measured values
    assert "PASS" in out                             # status names are not translated


def test_fmt_number():
    assert fmt_number(5.0146, "en") == "5.0146"
    assert fmt_number(5.0146, "de") == "5,0146"
    assert fmt_number(1000.0, "en") == "1000"
    assert fmt_number(0.000012345678, "en") == "1.23457e-05"


def test_text_tables_same_keys():
    assert TEXTS["en"].keys() == TEXTS["de"].keys()


def test_signature_boxes():
    p = load(FIXTURES / "itk_rma.json")
    out = render(p)
    signatures = out.split('id="signatures"', 1)[1]
    assert "jdoe" in signatures
    assert "Approved by" not in signatures
    assert "Approved by" in render(p, approver=True).split('id="signatures"', 1)[1]


def test_attachment_truncated():
    log = "\n".join(f"line {n}" for n in range(1, 501))
    p = Protocol(header={"serial": "S"}, groups=[Group("g", [Item("a", "PASS")])],
                 attachments=[Attachment("Console log", log)])
    out = render(p)
    assert "line 1\n" not in out
    assert "line 500" in out
    assert "line 301" in out and "line 300\n" not in out
    assert "last 200 of 500 lines" in out


def test_limit_source_marker():
    p = load(FIXTURES / "bench_pass.json")
    apply_limits(p, [Limit("5V0", low=4.0, high=6.0)], "limits.toml")
    out = render(p)
    assert "(limits.toml)" in out


def test_info_and_missing_limits_visible():
    p = Protocol(header={"serial": "S"}, groups=[Group("g", [Item("temp", "INFO", value=41.5)])])
    out = render(p)
    assert "INFO" in out
    assert "—" in out


def test_traceability_lists_inputs():
    out = render(load(FIXTURES / "bench_pass.json"))
    trace = out.split('id="traceability"', 1)[1]
    assert "bench_pass.json" in trace
    assert re.search(r"[0-9a-f]{64}", trace)
    assert "0.1.0" in trace
    assert "2026-10-29" in trace


def test_logo_and_meta():
    p = load(FIXTURES / "bench_pass.json")
    p.header["order"] = "4711"
    out = render(p, logo="data:image/png;base64,AAAA", company="ACME")
    assert '<img class="logo" src="data:image/png;base64,AAAA"' in out
    assert "order" in out and "4711" in out


def test_no_external_urls():
    out = render(load(FIXTURES / "bench_fail.json"))
    assert "http://" not in out and "https://" not in out


def test_print_css():
    out = render(load(FIXTURES / "bench_pass.json"))
    assert "size: A4" in out
    assert "counter(pages)" in out
    assert "@media screen and (prefers-color-scheme: dark)" in out
