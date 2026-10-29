"""Texts of the rendered protocol in English and German."""

from __future__ import annotations

TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "title": "Test protocol",
        "serial": "Serial number", "product": "Product", "station": "Station",
        "operator": "Operator", "started": "Started", "finished": "Finished",
        "rma": "RMA number", "profile": "Test profile", "mode": "Mode",
        "details": "Unit under test", "summary": "Summary", "results": "Results",
        "attachments": "Attachments", "traceability": "Traceability", "signatures": "Signatures",
        "failures": "Failed checks", "group": "Step", "item": "Check", "value": "Value",
        "limits": "Limits", "status": "Result", "message": "Note", "range": "Position in range",
        "source": "Source", "file": "File", "format": "Format", "sha256": "SHA-256",
        "tool": "Created with", "generated": "Created",
        "tested_by": "Tested by", "approved_by": "Approved by",
        "name": "Name", "date": "Date", "signature": "Signature",
        "truncated": "last {shown} of {total} lines",
        "page": "Page", "step_failed": "step failed", "only": "Partial run (steps)",
        "not_evaluated_1": "1 value without limits — not evaluated",
        "not_evaluated_n": "{n} values without limits — not evaluated",
    },
    "de": {
        "title": "Prüfprotokoll",
        "serial": "Seriennummer", "product": "Produkt", "station": "Prüfplatz",
        "operator": "Prüfer", "started": "Beginn", "finished": "Ende",
        "rma": "RMA-Nummer", "profile": "Prüfprofil", "mode": "Modus",
        "details": "Prüfling", "summary": "Zusammenfassung", "results": "Ergebnisse",
        "attachments": "Anhänge", "traceability": "Rückverfolgbarkeit", "signatures": "Unterschriften",
        "failures": "Fehlgeschlagene Prüfungen", "group": "Schritt", "item": "Prüfung",
        "value": "Messwert", "limits": "Grenzwerte", "status": "Ergebnis", "message": "Hinweis",
        "range": "Lage im Toleranzband", "source": "Quelle", "file": "Datei", "format": "Format",
        "sha256": "SHA-256", "tool": "Erstellt mit", "generated": "Erstellt am",
        "tested_by": "Geprüft von", "approved_by": "Freigegeben von",
        "name": "Name", "date": "Datum", "signature": "Unterschrift",
        "truncated": "letzte {shown} von {total} Zeilen",
        "page": "Seite", "step_failed": "Schritt fehlgeschlagen", "only": "Teillauf (Schritte)",
        "not_evaluated_1": "1 Wert ohne Grenzwerte — nicht bewertet",
        "not_evaluated_n": "{n} Werte ohne Grenzwerte — nicht bewertet",
    },
}


def t(lang: str, key: str) -> str:
    return TEXTS[lang][key]


def fmt_number(v: float, lang: str) -> str:
    text = repr(float(v))
    if text.endswith(".0"):
        text = text[:-2]
    return text.replace(".", ",") if lang == "de" else text
