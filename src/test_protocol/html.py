"""Render a Protocol as a self-contained, print-ready HTML page."""

from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import datetime

from .i18n import fmt_number, t
from .model import STATUSES, Group, Item, Protocol, as_number

HEADER_KEYS = ("serial", "product", "station", "operator", "started", "finished",
               "rma", "profile", "mode")
MAX_ATTACHMENT_LINES = 200
_STATUS_COLORS = {"PASS": "#1a7f37", "FAIL": "#cf222e", "ERROR": "#9a6700",
                  "SKIP": "#6e7781", "INFO": "#0969da"}


@dataclass
class RenderOptions:
    lang: str = "en"
    title: str | None = None
    company: str | None = None
    logo: str | None = None
    approver: bool = False
    tool_version: str = ""
    generated: datetime | None = None


def _e(value: object) -> str:
    return html.escape(str(value))


def _css_string(text: str) -> str:
    """Text as the inside of a CSS string; also safe inside <style>."""
    return "".join(c if c.isalnum() or c in " -_.:/" else f"\\{ord(c):x} " for c in text)


def _time(value: str) -> str:
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return value
    text = dt.strftime("%Y-%m-%d %H:%M:%S")
    return f"{text} {dt.strftime('%z')[:3]}:{dt.strftime('%z')[3:]}" if dt.tzinfo else text


def _badge(status: str) -> str:
    return f'<span class="badge" style="background:{_STATUS_COLORS[status]}">{status}</span>'


def _num(value: object, lang: str) -> str:
    number = as_number(value)
    if number is None or isinstance(value, str):
        return _e(value)
    return fmt_number(number, lang)


def _value(item: Item, lang: str) -> str:
    if item.value is None:
        return ""
    unit = f" {_e(item.unit)}" if item.unit else ""
    return f"{_num(item.value, lang)}{unit}"


def _limits(item: Item, lang: str) -> str:
    if item.expect is not None:
        text = f"= {_e(item.expect)}"
    elif item.low is not None and item.high is not None:
        text = (f"{fmt_number(item.low, lang)} … {fmt_number(item.high, lang)}"
                if item.low != item.high else f"= {fmt_number(item.low, lang)}")
    elif item.low is not None:
        text = f"≥ {fmt_number(item.low, lang)}"
    elif item.high is not None:
        text = f"≤ {fmt_number(item.high, lang)}"
    else:
        return "—"
    if item.limit_source:
        text += f' <span class="muted">({_e(item.limit_source)})</span>'
    return text


def _gauge(item: Item) -> str:
    """Small inline SVG showing where a value sits inside its tolerance band."""
    value = as_number(item.value)
    low, high = item.low, item.high
    if value is None or isinstance(item.value, str) or low is None or high is None or low >= high:
        return ""
    span = high - low
    lo, hi = low - span * 0.5, high + span * 0.5

    def x(v: float) -> float:
        return 4 + 112 * (min(max(v, lo), hi) - lo) / (hi - lo)

    color = _STATUS_COLORS["PASS" if low <= value <= high else "FAIL"]
    return (f'<svg width="120" height="14" role="img" aria-label="{_e(value)} in {low}..{high}">'
            f'<rect x="4" y="5" width="112" height="4" rx="2" fill="var(--track)"/>'
            f'<rect x="{x(low):.1f}" y="3" width="{x(high) - x(low):.1f}" height="8" rx="2" '
            f'fill="var(--band)"/>'
            f'<circle cx="{x(value):.1f}" cy="7" r="4.5" fill="{color}"/></svg>')


def _header(p: Protocol, opts: RenderOptions, title: str) -> str:
    verdict = p.verdict()
    logo = f'<img class="logo" src="{_e(opts.logo)}" alt="">' if opts.logo else ""
    company = f'<div class="company">{_e(opts.company)}</div>' if opts.company else ""
    serial = _e(p.header.get("serial", ""))
    return (f'<header id="header"><div class="brand">{logo}{company}</div>'
            f'<div class="heading"><h1>{_e(title)}</h1><div class="muted">{serial}</div></div>'
            f'<div class="verdict {verdict.lower()}">{verdict}</div></header>')


def _details(p: Protocol, lang: str) -> str:
    keys = [k for k in HEADER_KEYS if p.header.get(k)] + \
        [k for k in p.header if k not in HEADER_KEYS and p.header[k]]
    rows = []
    for key in keys:
        label = t(lang, key) if key in HEADER_KEYS else key
        value = _time(p.header[key]) if key in ("started", "finished") else p.header[key]
        rows.append(f"<tr><th>{_e(label)}</th><td>{_e(value)}</td></tr>")
    return (f'<section id="details"><h2>{t(lang, "details")}</h2>'
            f'<table class="kv">{"".join(rows)}</table></section>')


def _summary(p: Protocol, lang: str) -> str:
    counts = " ".join(f"{_badge(s)} {n}" for s, n in p.counts().items() if n)
    failures = p.failures()
    table = ""
    if failures:
        rows = []
        for group, item in failures:
            if item is None:
                rows.append(f"<tr><td>{_e(group.name)}</td><td>{t(lang, 'step_failed')}</td>"
                            f"<td></td><td></td><td>{_e(group.message)}</td>"
                            f"<td>{_badge(group.status or 'FAIL')}</td></tr>")
            else:
                rows.append(f"<tr><td>{_e(group.name)}</td><td>{_e(item.name)}</td>"
                            f'<td class="num">{_value(item, lang)}</td>'
                            f'<td class="num">{_limits(item, lang)}</td>'
                            f"<td>{_e(item.message)}</td><td>{_badge(item.status or 'FAIL')}</td></tr>")
        table = (f'<h3>{t(lang, "failures")}</h3><table class="grid"><thead><tr>'
                 f'<th>{t(lang, "group")}</th><th>{t(lang, "item")}</th>'
                 f'<th>{t(lang, "value")}</th><th>{t(lang, "limits")}</th>'
                 f'<th>{t(lang, "message")}</th><th>{t(lang, "status")}</th></tr></thead>'
                 f'<tbody>{"".join(rows)}</tbody></table>')
    return (f'<section id="summary"><h2>{t(lang, "summary")}</h2>'
            f'<p class="counts">{counts}</p>{table}</section>')


def _group(group: Group, lang: str) -> str:
    badge = f" {_badge(group.status)}" if group.status in STATUSES else ""
    note = f'<div class="note">{_e(group.message)}</div>' if group.message else ""
    source = f' <span class="muted">· {_e(group.source)}</span>' if group.source else ""
    rows = []
    for item in group.items:
        message = f'<div class="note">{_e(item.message)}</div>' if item.message else ""
        status = _badge(item.status) if item.status in STATUSES else ""
        rows.append(f"<tr><td>{_e(item.name)}{message}</td>"
                    f'<td class="num">{_value(item, lang)}</td>'
                    f'<td class="num">{_limits(item, lang)}</td>'
                    f"<td>{_gauge(item)}</td><td>{status}</td></tr>")
    table = ""
    if rows:
        table = (f'<table class="grid"><thead><tr><th>{t(lang, "item")}</th>'
                 f'<th>{t(lang, "value")}</th><th>{t(lang, "limits")}</th>'
                 f'<th>{t(lang, "range")}</th><th>{t(lang, "status")}</th></tr></thead>'
                 f'<tbody>{"".join(rows)}</tbody></table>')
    return (f'<div class="group"><h3>{_e(group.name)}{badge}{source}</h3>{note}{table}</div>')


def _attachments(p: Protocol, lang: str) -> str:
    blocks = []
    for att in p.attachments:
        lines = att.text.rstrip("\n").split("\n")
        note = ""
        if len(lines) > MAX_ATTACHMENT_LINES:
            note = (f' <span class="muted">({t(lang, "truncated").format(shown=MAX_ATTACHMENT_LINES, total=len(lines))})</span>')
            lines = lines[-MAX_ATTACHMENT_LINES:]
        text = "\n".join(lines)
        blocks.append(f"<details><summary>{_e(att.title)}{note}</summary>"
                      f"<pre>{_e(text)}</pre></details>")
    return (f'<section id="attachments"><h2>{t(lang, "attachments")}</h2>'
            f'{"".join(blocks) or "<p>—</p>"}</section>')


def _traceability(p: Protocol, opts: RenderOptions) -> str:
    lang = opts.lang
    rows = "".join(f"<tr><td>{_e(i.name)}</td><td>{_e(i.format)}</td>"
                   f'<td class="hash">{_e(i.sha256)}</td></tr>' for i in p.inputs)
    generated = (opts.generated or datetime.now().astimezone()).isoformat(timespec="seconds")
    return (f'<section id="traceability"><h2>{t(lang, "traceability")}</h2>'
            f'<table class="grid"><thead><tr><th>{t(lang, "file")}</th>'
            f'<th>{t(lang, "format")}</th><th>{t(lang, "sha256")}</th></tr></thead>'
            f"<tbody>{rows}</tbody></table>"
            f'<p class="muted">{t(lang, "tool")} test-protocol {_e(opts.tool_version)} · '
            f'{t(lang, "generated")} {_e(_time(generated))}</p></section>')


def _signature_box(heading: str, name: str, lang: str) -> str:
    return (f'<div class="sign"><h3>{heading}</h3>'
            f'<div class="line"><span>{t(lang, "name")}</span><b>{_e(name)}</b></div>'
            f'<div class="line"><span>{t(lang, "date")}</span><b></b></div>'
            f'<div class="line tall"><span>{t(lang, "signature")}</span><b></b></div></div>')


def _signatures(p: Protocol, opts: RenderOptions) -> str:
    lang = opts.lang
    boxes = _signature_box(t(lang, "tested_by"), p.header.get("operator", ""), lang)
    if opts.approver:
        boxes += _signature_box(t(lang, "approved_by"), "", lang)
    return (f'<section id="signatures"><h2>{t(lang, "signatures")}</h2>'
            f'<div class="signs">{boxes}</div></section>')


_CSS = """
:root { --bg:#fff; --fg:#1f2328; --muted:#656d76; --line:#d0d7de; --track:#d0d7de; --band:#aceebb; --head:#f6f8fa; }
@media screen and (prefers-color-scheme: dark) {
  :root { --bg:#0d1117; --fg:#e6edf3; --muted:#8d96a0; --line:#30363d; --track:#30363d; --band:#2b5a37; --head:#161b22; }
}
@page { size: A4; margin: 18mm 15mm 20mm; @bottom-center { content: "FOOTER" counter(page) " / " counter(pages); font: 9pt system-ui, sans-serif; color: #656d76; } }
* { box-sizing: border-box; }
body { background:var(--bg); color:var(--fg); font:14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; max-width:960px; margin:2rem auto; padding:0 16px; }
h1 { margin:0; font-size:24px; } h2 { font-size:17px; margin:1.6rem 0 .5rem; border-bottom:1px solid var(--line); padding-bottom:3px; }
h3 { font-size:14px; margin:1rem 0 .3rem; break-after:avoid; }
.group .note { break-after:avoid; }
.muted { color:var(--muted); font-weight:normal; }
header { display:flex; align-items:center; gap:16px; border-bottom:2px solid var(--fg); padding-bottom:10px; }
.brand { display:flex; align-items:center; gap:10px; } .logo { max-height:48px; max-width:160px; }
.company { font-weight:600; } .heading { flex:1; }
.verdict { font-size:26px; font-weight:700; color:#fff; padding:4px 18px; border-radius:6px; }
.verdict.pass { background:#1a7f37; } .verdict.fail { background:#cf222e; }
.badge { color:#fff; border-radius:4px; padding:1px 7px; font-size:11px; font-weight:600; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
table { width:100%; border-collapse:collapse; }
.grid th, .grid td, .kv th, .kv td { border-bottom:1px solid var(--line); padding:5px 8px; text-align:left; vertical-align:top; }
.grid th { background:var(--head); font-size:12px; } .kv th { width:30%; font-weight:600; }
tr { break-inside:avoid; }
.num { font-variant-numeric:tabular-nums; white-space:nowrap; }
.hash { font-family:ui-monospace, monospace; font-size:11px; word-break:break-all; }
.note { color:var(--muted); font-size:12px; }
.counts .badge { margin-left:10px; } .counts .badge:first-child { margin-left:0; }
pre { background:rgba(127,127,127,.1); padding:10px; overflow-x:auto; font-size:11.5px; white-space:pre-wrap; }
.signs { display:flex; gap:24px; break-inside:avoid; } .sign { flex:1; }
.line { display:flex; align-items:flex-end; gap:8px; margin:14px 0; } .line span { width:90px; color:var(--muted); font-size:12px; }
.line b { flex:1; border-bottom:1px solid var(--fg); min-height:20px; font-weight:normal; } .line.tall b { min-height:44px; }
#signatures { break-inside:avoid; }
@media print {
  body { margin:0; max-width:none; padding:0; font-size:11pt; }
  details > summary { list-style:none; } details > summary::-webkit-details-marker { display:none; }
  details::details-content { content-visibility:visible; display:block; }
  .verdict, .badge { -webkit-print-color-adjust:exact; print-color-adjust:exact; }
}
"""

def render_html(p: Protocol, opts: RenderOptions) -> str:
    lang = opts.lang
    title = opts.title or t(lang, "title")
    footer = _css_string(f"{p.header.get('serial', '')} · {t(lang, 'page')} ")
    css = _CSS.replace('"FOOTER"', f'"{footer}"')
    results = "".join(_group(g, lang) for g in p.groups)
    serial = p.header.get("serial", "")
    return f"""<!doctype html>
<html lang="{_e(lang)}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(title)} {_e(serial)}</title>
<style>{css}</style></head><body>
{_header(p, opts, title)}
{_details(p, lang)}
{_summary(p, lang)}
<section id="results"><h2>{t(lang, "results")}</h2>{results}</section>
{_attachments(p, lang)}
{_traceability(p, opts)}
{_signatures(p, opts)}
</body></html>
"""
