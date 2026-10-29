"""Turn the rendered HTML into a PDF with WeasyPrint or a headless Chromium-based browser."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ENV_BROWSER = "TEST_PROTOCOL_BROWSER"
_NAMES = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "chrome",
          "msedge", "microsoft-edge")
_MAC_APPS = ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
             "/Applications/Chromium.app/Contents/MacOS/Chromium",
             "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge")
_WINDOWS_APPS = (r"Google\Chrome\Application\chrome.exe",
                 r"Microsoft\Edge\Application\msedge.exe")


class PdfError(Exception):
    pass


def find_browser() -> str | None:
    env = os.environ.get(ENV_BROWSER)
    if env:
        if not Path(env).is_file():
            raise PdfError(f"{ENV_BROWSER}={env} does not exist")
        return env
    for name in _NAMES:
        found = shutil.which(name)
        if found:
            return found
    candidates: list[str] = []
    if sys.platform == "darwin":
        candidates += _MAC_APPS
    elif sys.platform == "win32":
        for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"),
                     os.environ.get("LOCALAPPDATA")):
            if base:
                candidates += [os.path.join(base, app) for app in _WINDOWS_APPS]
    return next((c for c in candidates if Path(c).is_file()), None)


def _weasyprint(html_text: str, out: Path) -> bool:
    try:
        import weasyprint
    except (ImportError, OSError):     # OSError: native libraries (Pango) missing
        return False
    weasyprint.HTML(string=html_text).write_pdf(out)
    return True


def _chrome(browser: str, html_text: str, out: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="test-protocol-") as tmp:
        page = Path(tmp) / "protocol.html"
        page.write_text(html_text, encoding="utf-8")
        cmd = [browser, "--headless", "--disable-gpu", "--no-pdf-header-footer",
               f"--user-data-dir={Path(tmp) / 'profile'}",
               f"--print-to-pdf={out.resolve()}", page.as_uri()]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise PdfError(f"{browser}: {e}") from None
        if result.returncode != 0 or not out.is_file() or out.stat().st_size == 0:
            tail = "\n".join((result.stderr or "").strip().splitlines()[-5:])
            raise PdfError(f"{browser} could not print the PDF (exit {result.returncode}): {tail}")


def write_pdf(html_text: str, out: Path, engine: str = "auto") -> str:
    out = Path(out)
    if engine in ("auto", "weasyprint") and _weasyprint(html_text, out):
        return "weasyprint"
    if engine == "weasyprint":
        raise PdfError("WeasyPrint is not available: pip install 'test-protocol[pdf]'")
    browser = find_browser()
    if browser is None:
        raise PdfError("no PDF engine: install 'test-protocol[pdf]' or Chrome/Chromium/Edge, "
                       f"or set {ENV_BROWSER}")
    _chrome(browser, html_text, out)
    return "chrome"
