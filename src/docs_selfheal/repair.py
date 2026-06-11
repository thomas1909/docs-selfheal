"""Doc repair engine: targeted corrections, confidence-driven mode selection.

Simple, mechanical staleness (an old signature quoted verbatim) is auto-fixed.
Anything semantic gets a draft with explicit TODO markers and goes to human
review. An LLM rewriter can replace `rewrite_section` behind the same signature.
"""

from __future__ import annotations

from .schemas import (
    ChangeType,
    CodeChange,
    Correction,
    CorrectionMode,
    DocSection,
    StalenessReport,
    Verdict,
)

AUTO_FIX_CONFIDENCE = 0.85


def rewrite_section(
    section: DocSection, change: CodeChange, report: StalenessReport
) -> Correction:
    content = section.content
    if (change.change_type == ChangeType.signature_changed
            and change.old is not None and change.new is not None
            and change.old.signature in content):
        corrected = content.replace(change.old.signature, change.new.signature)
        return Correction(
            section_id=section.section_id,
            mode=CorrectionMode.auto_fix,
            original_content=content,
            corrected_content=corrected,
            explanation=(f"Remplacement mécanique de la signature obsolète "
                         f"`{change.old.signature}` par `{change.new.signature}`."),
        )
    if change.change_type == ChangeType.removed and change.old is not None:
        todo = (f"\n\n> **TODO(docheal)** : `{change.old.name}` a été supprimé du code. "
                f"Cette section doit être réécrite ou supprimée.")
        return Correction(
            section_id=section.section_id,
            mode=CorrectionMode.human_review,
            original_content=content,
            corrected_content=content + todo,
            explanation=f"`{change.old.name}` n'existe plus ; revue humaine requise.",
        )
    todo = ("\n\n> **TODO(docheal)** : le code lié a changé "
            f"({change.change_type.value}) ; vérifier que cette section est à jour.")
    return Correction(
        section_id=section.section_id,
        mode=CorrectionMode.human_review,
        original_content=content,
        corrected_content=content + todo,
        explanation=report.reason,
    )


def plan_corrections(
    reports: list[StalenessReport],
    sections: list[DocSection],
    changes: list[CodeChange],
) -> list[Correction]:
    by_section = {s.section_id: s for s in sections}
    by_chunk = {c.chunk_id: c for c in changes}
    corrections: list[Correction] = []
    for report in reports:
        if report.verdict == Verdict.accurate:
            continue
        section = by_section.get(report.section_id)
        change = by_chunk.get(report.chunk_id)
        if section is None or change is None:
            continue
        correction = rewrite_section(section, change, report)
        # The confidence gate decides the mode, never the other way around.
        if (correction.mode == CorrectionMode.auto_fix
                and report.confidence < AUTO_FIX_CONFIDENCE):
            correction.mode = CorrectionMode.human_review
        corrections.append(correction)
    return corrections


def validate_correction(correction: Correction, change: CodeChange) -> bool:
    """Quality gate before opening a PR: the new content must mention the new
    signature (if any) and must not have lost the parts that were accurate."""
    if change.new is not None and change.change_type == ChangeType.signature_changed:
        if change.new.signature not in correction.corrected_content:
            return False
        if change.old is not None and change.old.signature in correction.corrected_content:
            return False
    # Cheap structure check: the correction must not shrink the section by half.
    return len(correction.corrected_content) >= len(correction.original_content) // 2
