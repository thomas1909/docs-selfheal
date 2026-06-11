"""CLI / GitHub Action entrypoint.

`docheal check --old <dir> --new <dir> --docs <dir>` compares two snapshots of
a codebase against the docs and emits the PR-comment summary (markdown) plus an
exit code: 0 clean, 1 stale sections found.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .code_parser import parse_codebase
from .diffing import diff_chunks, meaningful_changes
from .doc_parser import parse_docs_dir
from .linker import build_graph
from .repair import plan_corrections, validate_correction
from .schemas import CorrectionMode, Verdict
from .staleness import check_staleness


def summary_markdown(reports, corrections) -> str:
    accurate = sum(1 for r in reports if r.verdict == Verdict.accurate)
    auto = [c for c in corrections if c.mode == CorrectionMode.auto_fix]
    review = [c for c in corrections if c.mode == CorrectionMode.human_review]
    lines = [
        "## Doc Check Results",
        f"- ✅ {accurate} section(s) vérifiée(s) exacte(s)",
        f"- 🔧 {len(auto)} correction(s) automatique(s) proposée(s)",
        f"- 👀 {len(review)} section(s) à revoir manuellement",
    ]
    for c in auto:
        lines.append(f"  - auto-fix : `{c.section_id}` — {c.explanation}")
    for c in review:
        lines.append(f"  - revue : `{c.section_id}` — {c.explanation}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="docheal")
    sub = parser.add_subparsers(dest="command", required=True)
    p_check = sub.add_parser("check")
    p_check.add_argument("--old", type=Path, required=True)
    p_check.add_argument("--new", type=Path, required=True)
    p_check.add_argument("--docs", type=Path, required=True)
    p_check.add_argument("--out", type=Path, default=None,
                         help="écrit les corrections en JSON")
    args = parser.parse_args(argv)

    old_chunks = parse_codebase(args.old)
    new_chunks = parse_codebase(args.new)
    sections = parse_docs_dir(args.docs)
    graph = build_graph(old_chunks, sections)
    changes = meaningful_changes(diff_chunks(old_chunks, new_chunks))
    reports = check_staleness(changes, graph, sections)
    corrections = plan_corrections(reports, sections, changes)
    by_chunk = {c.chunk_id: c for c in changes}
    corrections = [
        c for c in corrections
        if validate_correction(
            c, by_chunk[next(r.chunk_id for r in reports if r.section_id == c.section_id)])
    ]

    print(summary_markdown(reports, corrections))
    if args.out:
        args.out.write_text(
            json.dumps([c.model_dump() for c in corrections], indent=2,
                       ensure_ascii=False),
            encoding="utf-8")
    return 1 if corrections else 0


if __name__ == "__main__":
    sys.exit(main())
