"""Typed contracts for the code<->docs graph and the repair pipeline."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ChunkKind(str, Enum):
    function = "function"
    klass = "class"
    method = "method"


class CodeChunk(BaseModel):
    """A semantic unit of code with a stable identifier (path::qualname)."""

    chunk_id: str
    file: str
    name: str
    kind: ChunkKind
    signature: str
    docstring: str = ""
    body_hash: str = ""


class DocSection(BaseModel):
    """A markdown section (split by headings) with extracted code references."""

    section_id: str          # "docs/api.md#configuration>variables"
    file: str
    heading_path: str
    content: str
    code_refs: list[str] = Field(default_factory=list)


class Link(BaseModel):
    section_id: str
    chunk_id: str
    via: str                 # "name-match" | "similarity"
    score: float = 1.0


class LinkGraph(BaseModel):
    links: list[Link] = Field(default_factory=list)

    def sections_for_chunk(self, chunk_id: str) -> list[str]:
        return sorted({lk.section_id for lk in self.links if lk.chunk_id == chunk_id})

    def chunks_for_section(self, section_id: str) -> list[str]:
        return sorted({lk.chunk_id for lk in self.links if lk.section_id == section_id})


class ChangeType(str, Enum):
    added = "added"
    removed = "removed"
    signature_changed = "signature_changed"
    body_changed = "body_changed"


class CodeChange(BaseModel):
    chunk_id: str
    change_type: ChangeType
    old: CodeChunk | None = None
    new: CodeChunk | None = None


class Verdict(str, Enum):
    accurate = "accurate"
    stale = "stale"
    needs_review = "needs_review"


class StalenessReport(BaseModel):
    section_id: str
    chunk_id: str
    verdict: Verdict
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)


class CorrectionMode(str, Enum):
    auto_fix = "auto_fix"          # high confidence: open a PR with the fix
    human_review = "human_review"  # low confidence: comment with TODO markers


class Correction(BaseModel):
    section_id: str
    mode: CorrectionMode
    original_content: str
    corrected_content: str
    explanation: str
