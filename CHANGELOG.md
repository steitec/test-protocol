# Changelog

## 0.1.0 — 2026-10-29

First release.

- Reads bench-automation and interface-test-kit `result.json`, JUnit XML
  (pytest, boot-log-diff, CI tools), CSV (also German Excel exports) and its
  own JSON; the format is detected from the file.
- Merges several result files of one unit into one protocol and stops if the
  serial numbers differ.
- Limits file in TOML sets or overrides limits and evaluates PASS/FAIL again;
  `--require-limits` fails measurements without a limit.
- Self-contained HTML protocol for A4 print: verdict, failed checks on top,
  results with the position in the tolerance band, attachments, input files
  with SHA-256, signature boxes; English or German.
- PDF via WeasyPrint (`test-protocol[pdf]`) or headless Chrome/Chromium/Edge.
- Normalized JSON (`test-protocol/1`) as interface for other tools.
- Exit status 0 PASS, 1 FAIL, 2 bad input.
