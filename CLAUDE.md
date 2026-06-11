# CLAUDE.md — Docs Selfheal (BASWE Project 4)

## Goal
GitHub Action that detects doc sections made stale by code changes (ast-based
code chunks <-> markdown sections link graph), verifies staleness, and proposes
confidence-gated corrections (auto-fix vs human review with TODO markers).

## Stack
Python 3.11 · `uv` · Pydantic v2 · ast (stdlib) · pytest · ruff. No LLM required
offline; LLM verifier/rewriter pluggable via Protocols.

## Modules (`src/docs_selfheal/`)
- **schemas.py** — CodeChunk (id=file::qualname, signature, body_hash),
  DocSection (heading_path, code_refs), Link/LinkGraph, CodeChange/ChangeType,
  StalenessReport/Verdict, Correction/CorrectionMode.
- **code_parser.py** — ast walk: functions/classes/methods, full signatures
  (annotations + defaults + *args/**kwargs), docstrings, sha1 body hash.
- **doc_parser.py** — markdown sections by heading stack; code refs from backticks.
- **linker.py** — name-match pass then lexical-similarity pass (threshold 0.45),
  dedup. `similarity()` is the embedding swap point.
- **diffing.py** — diff_chunks (removed/signature_changed/body_changed/added),
  meaningful_changes (priority ordering). Comment/whitespace churn invisible.
- **staleness.py** — DeterministicVerifier: removed+mentioned -> stale (0.95);
  signature changed + old sig quoted -> stale (0.9) else needs_review (0.55);
  body changed -> needs_review (0.4). `Verifier` protocol for LLM.
- **repair.py** — rewrite_section (mechanical sig replacement -> auto_fix;
  otherwise TODO(docheal) draft -> human_review), AUTO_FIX_CONFIDENCE=0.85 gate,
  validate_correction (new sig present, old sig gone, no half-shrink).
- **cli.py** — `docheal check --old --new --docs [--out]` -> markdown summary,
  exit 1 when stale. `action.yml` = composite GitHub Action wrapper.

## Commands
```bash
uv sync --extra dev --link-mode=copy
uv run --no-sync pytest -v
uv run --no-sync ruff check .
```

## Hard rules
- Diff on ast-derived data only — formatting churn must never flag docs.
- auto_fix only when old signature is quoted verbatim AND confidence >= 0.85.
- Corrections never rewrite accurate parts — targeted replacement or appended TODO.
- ruff + pytest green before stopping.
