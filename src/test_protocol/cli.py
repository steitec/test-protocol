"""Command line: test-protocol INPUT... [-o protocol.html] [--pdf protocol.pdf] [--json data.json]"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from pathlib import Path

from . import __version__, jsonio
from .html import RenderOptions, render_html
from .i18n import TEXTS, fmt_number
from .limits import apply_limits, load_limits, require_limits
from .merge import merge
from .model import InputError, InputFile, Item, Protocol
from .pdf import PdfError, write_pdf
from .readers import FORMATS, load

_LOGO_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".svg": "image/svg+xml"}


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="test-protocol",
        description="Turn raw test results of one device into a printable test protocol.")
    ap.add_argument("inputs", nargs="+", metavar="INPUT",
                    help="result files: bench-automation or interface-test-kit result.json, "
                         "JUnit XML, CSV, or test-protocol JSON")
    ap.add_argument("-o", "--html", metavar="FILE", help="write the protocol as HTML")
    ap.add_argument("--pdf", metavar="FILE", help="write the protocol as PDF")
    ap.add_argument("--json", metavar="FILE", help="write the normalized data as JSON")
    ap.add_argument("--limits", metavar="FILE", help="TOML file that sets or overrides limits")
    ap.add_argument("--require-limits", action="store_true",
                    help="fail every measurement that has no limit")
    ap.add_argument("--serial", help="serial number (must match the inputs)")
    ap.add_argument("--product", help="product or variant name")
    ap.add_argument("--station", help="test station")
    ap.add_argument("--operator", help="person who ran the test")
    ap.add_argument("--meta", action="append", default=[], metavar="KEY=VALUE",
                    help="extra field for the protocol header (repeatable)")
    ap.add_argument("--title", help="protocol title (default: 'Test protocol')")
    ap.add_argument("--company", help="company name in the header")
    ap.add_argument("--logo", metavar="FILE", help="logo (PNG, JPEG or SVG) in the header")
    ap.add_argument("--approver", action="store_true", help="add an 'Approved by' signature box")
    ap.add_argument("--lang", choices=sorted(TEXTS), default="en", help="protocol language")
    ap.add_argument("--format", choices=FORMATS, default="auto", help="input format")
    ap.add_argument("--pdf-engine", choices=("auto", "weasyprint", "chrome"), default="auto",
                    help="PDF engine (default: WeasyPrint if installed, else Chrome/Chromium/Edge)")
    ap.add_argument("--version", action="version", version=f"test-protocol {__version__}")
    return ap


def _header(args: argparse.Namespace) -> dict[str, str]:
    header = {key: getattr(args, key) for key in ("serial", "product", "station", "operator")
              if getattr(args, key)}
    for meta in args.meta:
        key, sep, value = meta.partition("=")
        if not sep or not key.strip():
            raise InputError(f"--meta {meta!r}: use KEY=VALUE")
        header[key.strip()] = value.strip()
    return header


def _logo(path: str) -> str:
    file = Path(path)
    mime = _LOGO_TYPES.get(file.suffix.lower())
    if mime is None:
        raise InputError(f"logo {file.name}: use a PNG, JPEG or SVG file")
    try:
        data = file.read_bytes()
    except OSError as e:
        raise InputError(f"logo {file.name}: {e.strerror or e}") from None
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def _limit_text(item: Item) -> str:
    if item.expect is not None:
        return f"= {item.expect}"
    if item.low is not None and item.high is not None:
        return f"{fmt_number(item.low, 'en')} … {fmt_number(item.high, 'en')}"
    if item.low is not None:
        return f"≥ {fmt_number(item.low, 'en')}"
    if item.high is not None:
        return f"≤ {fmt_number(item.high, 'en')}"
    return ""


def _summary(p: Protocol) -> str:
    lines = [f"{p.header['serial']}: {p.verdict()}",
             "  ".join(f"{status} {n}" for status, n in p.counts().items() if n)]
    for group, item in p.failures():
        if item is None:
            text, status = f"{group.name}: step failed", group.status
            message = f"— {group.message}" if group.message else ""
        else:
            value = "" if item.value is None else \
                f" {item.value}{' ' + item.unit if item.unit else ''}"
            limits = _limit_text(item)
            text = f"{group.name} / {item.name}:{value}{f' ({limits})' if limits else ''}"
            message, status = item.message, item.status
        lines.append(f"  {status:<5} {text}{' ' + message if message else ''}")
    return "\n".join(lines)


def _add_limits(protocol: Protocol, file: str) -> None:
    path = Path(file)
    for lim in apply_limits(protocol, load_limits(path), path.name):
        print(f"test-protocol: warning: limit '{lim.measurement}' matched no measurement",
              file=sys.stderr)
    protocol.inputs.append(InputFile(path.name, hashlib.sha256(path.read_bytes()).hexdigest(),
                                     "limits"))


def run(args: argparse.Namespace) -> int:
    header = _header(args)
    logo = _logo(args.logo) if args.logo else None
    protocol = merge([load(Path(i), args.format) for i in args.inputs], header)
    if not protocol.items() and not any(g.status for g in protocol.groups):
        raise InputError("no test results in the input")
    if not protocol.header.get("serial"):
        raise InputError("no serial number found; use --serial")
    if args.limits:
        _add_limits(protocol, args.limits)
    if args.require_limits:
        require_limits(protocol)
    counts = protocol.counts()
    if counts["PASS"] + counts["FAIL"] + counts["ERROR"] == 0:
        raise InputError("no evaluated checks: every result is INFO or SKIP; "
                         "add limits or use --require-limits")

    written = []
    if args.json:
        Path(args.json).write_text(json.dumps(jsonio.to_dict(protocol), indent=2,
                                              ensure_ascii=False) + "\n", encoding="utf-8")
        written.append(args.json)
    if args.html or args.pdf:
        html_text = render_html(protocol, RenderOptions(
            lang=args.lang, title=args.title, company=args.company, logo=logo,
            approver=args.approver, tool_version=__version__))
        if args.html:
            Path(args.html).write_text(html_text, encoding="utf-8")
            written.append(args.html)
        if args.pdf:
            write_pdf(html_text, Path(args.pdf), args.pdf_engine)
            written.append(args.pdf)
    if written:
        print(f"{protocol.header['serial']}: {protocol.verdict()}")
        for path in written:
            print(f"  wrote {path}")
    else:
        print(_summary(protocol))
    return 0 if protocol.verdict() == "PASS" else 1


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return run(args)
    except (InputError, PdfError) as e:
        print(f"test-protocol: error: {e}", file=sys.stderr)
    except OSError as e:
        print(f"test-protocol: error: {e.filename or ''}: {e.strerror or e}", file=sys.stderr)
    return 2
