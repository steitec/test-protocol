import builtins
import subprocess
from pathlib import Path

import pytest

from test_protocol import pdf
from test_protocol.html import RenderOptions, render_html
from test_protocol.readers import load

FIXTURES = Path(__file__).parent / "fixtures"


def sample_html() -> str:
    return render_html(load(FIXTURES / "bench_fail.json"), RenderOptions(tool_version="0.1.0"))


def has_weasyprint() -> bool:
    try:
        import weasyprint  # noqa: F401
    except (ImportError, OSError):
        return False
    return True


@pytest.fixture
def no_weasyprint(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "weasyprint":
            raise ImportError("no weasyprint")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)


def test_no_engine_error(no_weasyprint, monkeypatch, tmp_path):
    monkeypatch.setattr(pdf, "find_browser", lambda: None)
    with pytest.raises(pdf.PdfError, match="no PDF engine"):
        pdf.write_pdf("<p>x</p>", tmp_path / "x.pdf")


def test_weasyprint_requested_but_missing(no_weasyprint, tmp_path):
    with pytest.raises(pdf.PdfError, match=r"test-protocol\[pdf\]"):
        pdf.write_pdf("<p>x</p>", tmp_path / "x.pdf", engine="weasyprint")


def test_env_browser_wins(monkeypatch, tmp_path):
    fake = tmp_path / "my-chrome"
    fake.write_text("")
    monkeypatch.setenv("TEST_PROTOCOL_BROWSER", str(fake))
    assert pdf.find_browser() == str(fake)


def test_env_browser_missing_is_error(monkeypatch, tmp_path):
    monkeypatch.setenv("TEST_PROTOCOL_BROWSER", str(tmp_path / "nope"))
    with pytest.raises(pdf.PdfError, match="TEST_PROTOCOL_BROWSER"):
        pdf.find_browser()


def test_chrome_command(monkeypatch, tmp_path):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        out = next(a for a in cmd if a.startswith("--print-to-pdf=")).split("=", 1)[1]
        Path(out).write_bytes(b"%PDF-1.7 fake")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(pdf, "find_browser", lambda: "/opt/chrome")
    monkeypatch.setattr(pdf.subprocess, "run", fake_run)
    out = tmp_path / "out.pdf"
    assert pdf.write_pdf("<p>x</p>", out, engine="chrome") == "chrome"
    cmd, kwargs = calls[0]
    assert cmd[0] == "/opt/chrome"
    assert {"--headless", "--disable-gpu", "--no-pdf-header-footer"} <= set(cmd)
    assert cmd[-1].startswith("file:")
    assert kwargs["timeout"] == 60
    assert out.read_bytes().startswith(b"%PDF")


def test_chrome_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(pdf, "find_browser", lambda: "/opt/chrome")
    monkeypatch.setattr(pdf.subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(
        cmd, 1, "", "line1\nsandbox crashed\n"))
    with pytest.raises(pdf.PdfError, match="sandbox crashed"):
        pdf.write_pdf("<p>x</p>", tmp_path / "x.pdf", engine="chrome")


@pytest.mark.skipif(not has_weasyprint(), reason="WeasyPrint not installed")
def test_weasyprint_real(tmp_path):
    out = tmp_path / "w.pdf"
    assert pdf.write_pdf(sample_html(), out, engine="weasyprint") == "weasyprint"
    assert out.read_bytes().startswith(b"%PDF")


@pytest.mark.skipif(pdf.find_browser() is None, reason="no Chrome/Chromium/Edge")
def test_chrome_real(tmp_path):
    out = tmp_path / "c.pdf"
    assert pdf.write_pdf(sample_html(), out, engine="chrome") == "chrome"
    assert out.read_bytes().startswith(b"%PDF")
