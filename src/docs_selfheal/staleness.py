"""Staleness verification: is a linked doc section still accurate after a change?

The deterministic checker covers the high-precision cases (renamed/removed
symbols, signature drift visible in the section text). An LLM verifier can be
plugged in via the `Verifier` protocol for the semantic cases.
"""

from __future__ import annotations

import re
from typing import Protocol

from .schemas import (
    ChangeType,
    CodeChange,
    DocSection,
    LinkGraph,
    StalenessReport,
    Verdict,
)


class Verifier(Protocol):
    def verify(self, section: DocSection, change: CodeChange) -> StalenessReport: ...


class DeterministicVerifier:
    def verify(self, section: DocSection, change: CodeChange) -> StalenessReport:
        name = (change.old or change.new).name  # type: ignore[union-attr]
        mentions = (
            name in section.code_refs
            or any(ref.endswith("." + name) for ref in section.code_refs)
            or re.search(rf"\b{re.escape(name)}\b", section.content) is not None
        )
        if change.change_type == ChangeType.removed and mentions:
            return StalenessReport(
                section_id=section.section_id, chunk_id=change.chunk_id,
                verdict=Verdict.stale, confidence=0.95,
                reason=f"« {name} » a été supprimé du code mais la section le documente encore.")
        if change.change_type == ChangeType.signature_changed and mentions:
            old_sig, new_sig = change.old.signature, change.new.signature  # type: ignore[union-attr]
            quoted = old_sig in section.content
            return StalenessReport(
                section_id=section.section_id, chunk_id=change.chunk_id,
                verdict=Verdict.stale if quoted else Verdict.needs_review,
                confidence=0.9 if quoted else 0.55,
                reason=(f"signature changée : `{old_sig}` -> `{new_sig}`"
                        + ("" if quoted else " (ancienne signature non citée textuellement)")),
            )
        if change.change_type == ChangeType.body_changed and mentions:
            return StalenessReport(
                section_id=section.section_id, chunk_id=change.chunk_id,
                verdict=Verdict.needs_review, confidence=0.4,
                reason=f"le corps de « {name} » a changé ; comportement possiblement différent.")
        return StalenessReport(
            section_id=section.section_id, chunk_id=change.chunk_id,
            verdict=Verdict.accurate, confidence=0.7,
            reason="aucune mention affectée par ce changement.")


def find_suspects(
    changes: list[CodeChange],
    graph: LinkGraph,
    sections: list[DocSection],
) -> list[tuple[DocSection, CodeChange]]:
    by_id = {s.section_id: s for s in sections}
    suspects: list[tuple[DocSection, CodeChange]] = []
    for change in changes:
        for section_id in graph.sections_for_chunk(change.chunk_id):
            section = by_id.get(section_id)
            if section is not None:
                suspects.append((section, change))
    return suspects


def check_staleness(
    changes: list[CodeChange],
    graph: LinkGraph,
    sections: list[DocSection],
    verifier: Verifier | None = None,
) -> list[StalenessReport]:
    verifier = verifier or DeterministicVerifier()
    return [verifier.verify(section, change)
            for section, change in find_suspects(changes, graph, sections)]
