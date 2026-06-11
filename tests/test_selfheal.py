"""Code parsing, doc parsing, link graph, staleness detection, repair, CLI."""

import textwrap

from docs_selfheal.cli import main
from docs_selfheal.code_parser import parse_source
from docs_selfheal.diffing import diff_chunks, meaningful_changes
from docs_selfheal.doc_parser import parse_markdown
from docs_selfheal.linker import build_graph
from docs_selfheal.repair import plan_corrections, validate_correction
from docs_selfheal.schemas import ChangeType, CorrectionMode, Verdict
from docs_selfheal.staleness import check_staleness

OLD_CODE = textwrap.dedent('''
    def load_config(path: str) -> dict:
        """Load the YAML configuration."""
        return {}

    def send_email(to: str, subject: str) -> bool:
        """Send a notification email."""
        return True

    class Client:
        """API client."""

        def request(self, url: str) -> str:
            return ""
''')

NEW_CODE = textwrap.dedent('''
    def load_config(path: str, strict: bool = False) -> dict:
        """Load the YAML configuration."""
        return {}

    class Client:
        """API client."""

        def request(self, url: str, timeout: int = 30) -> str:
            return ""
''')

DOCS = textwrap.dedent('''
    # Guide

    ## Configuration

    Utilisez `load_config()` pour charger la configuration.
    La signature est `load_config(path: str) -> dict`.

    ## Notifications

    La fonction `send_email` envoie un email à l'utilisateur.

    ## Divers

    Cette section ne référence aucun code.
''')


def test_code_parser_extracts_chunks():
    chunks = parse_source(OLD_CODE, "app.py")
    ids = {c.chunk_id for c in chunks}
    assert "app.py::load_config" in ids
    assert "app.py::Client" in ids
    assert "app.py::Client.request" in ids
    sig = next(c for c in chunks if c.name == "load_config").signature
    assert sig == "load_config(path: str) -> dict"


def test_doc_parser_sections_and_refs():
    sections = parse_markdown(DOCS, "guide.md")
    paths = [s.heading_path for s in sections]
    assert "Guide > Configuration" in paths
    config = next(s for s in sections if "Configuration" in s.heading_path)
    assert "load_config" in config.code_refs


def test_link_graph_name_matching():
    chunks = parse_source(OLD_CODE, "app.py")
    sections = parse_markdown(DOCS, "guide.md")
    graph = build_graph(chunks, sections)
    linked = graph.sections_for_chunk("app.py::load_config")
    assert any("configuration" in s for s in linked)


def test_diff_detects_signature_change_and_removal():
    changes = diff_chunks(parse_source(OLD_CODE, "app.py"),
                          parse_source(NEW_CODE, "app.py"))
    by_type = {c.chunk_id: c.change_type for c in changes}
    assert by_type["app.py::load_config"] == ChangeType.signature_changed
    assert by_type["app.py::send_email"] == ChangeType.removed
    assert by_type["app.py::Client.request"] == ChangeType.signature_changed
    ordered = meaningful_changes(changes)
    assert ordered[0].change_type == ChangeType.removed


def test_staleness_detection():
    old = parse_source(OLD_CODE, "app.py")
    new = parse_source(NEW_CODE, "app.py")
    sections = parse_markdown(DOCS, "guide.md")
    graph = build_graph(old, sections)
    reports = check_staleness(diff_chunks(old, new), graph, sections)
    verdicts = {(r.section_id.split("#")[1], r.verdict) for r in reports}
    assert any("configuration" in sid and v == Verdict.stale for sid, v in verdicts)
    assert any("notifications" in sid and v == Verdict.stale for sid, v in verdicts)


def test_repair_auto_fixes_quoted_signature():
    old = parse_source(OLD_CODE, "app.py")
    new = parse_source(NEW_CODE, "app.py")
    sections = parse_markdown(DOCS, "guide.md")
    graph = build_graph(old, sections)
    changes = diff_chunks(old, new)
    reports = check_staleness(changes, graph, sections)
    corrections = plan_corrections(reports, sections, changes)
    auto = [c for c in corrections if c.mode == CorrectionMode.auto_fix]
    assert auto, "the quoted load_config signature must be auto-fixable"
    fixed = auto[0]
    assert "strict: bool = False" in fixed.corrected_content
    by_chunk = {c.chunk_id: c for c in changes}
    assert validate_correction(fixed, by_chunk["app.py::load_config"])


def test_removed_function_goes_to_human_review():
    old = parse_source(OLD_CODE, "app.py")
    new = parse_source(NEW_CODE, "app.py")
    sections = parse_markdown(DOCS, "guide.md")
    graph = build_graph(old, sections)
    changes = diff_chunks(old, new)
    reports = check_staleness(changes, graph, sections)
    corrections = plan_corrections(reports, sections, changes)
    review = [c for c in corrections if c.mode == CorrectionMode.human_review]
    assert any("TODO(docheal)" in c.corrected_content for c in review)


def test_cli_end_to_end(tmp_path, capsys):
    (tmp_path / "old").mkdir()
    (tmp_path / "new").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "old" / "app.py").write_text(OLD_CODE, encoding="utf-8")
    (tmp_path / "new" / "app.py").write_text(NEW_CODE, encoding="utf-8")
    (tmp_path / "docs" / "guide.md").write_text(DOCS, encoding="utf-8")
    out_file = tmp_path / "corrections.json"
    code = main(["check", "--old", str(tmp_path / "old"), "--new", str(tmp_path / "new"),
                 "--docs", str(tmp_path / "docs"), "--out", str(out_file)])
    assert code == 1  # stale docs found
    captured = capsys.readouterr().out
    assert "Doc Check Results" in captured
    assert out_file.exists()
