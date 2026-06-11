"""Build the code<->docs link graph.

Two passes, as in the build guide:
1. exact name matching (a section mentioning `load_config` links to that chunk);
2. lexical similarity for sections without explicit refs (token-overlap embedding
   stand-in — swap in real embeddings behind the same `similarity` function).
"""

from __future__ import annotations

import re

from .schemas import CodeChunk, DocSection, Link, LinkGraph

_WORD = re.compile(r"[a-z][a-z0-9_]{2,}")


def _tokens(text: str) -> set[str]:
    tokens = set(_WORD.findall(text.lower()))
    # split snake_case identifiers into their parts too
    for tok in list(tokens):
        if "_" in tok:
            tokens.update(p for p in tok.split("_") if len(p) > 2)
    return tokens


def similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def build_graph(
    chunks: list[CodeChunk],
    sections: list[DocSection],
    similarity_threshold: float = 0.45,
) -> LinkGraph:
    graph = LinkGraph()
    by_name: dict[str, list[CodeChunk]] = {}
    for chunk in chunks:
        by_name.setdefault(chunk.name, []).append(chunk)

    for section in sections:
        matched = False
        for ref in section.code_refs:
            base = ref.split(".")[-1]
            for chunk in by_name.get(base, []) + by_name.get(ref, []):
                graph.links.append(Link(
                    section_id=section.section_id, chunk_id=chunk.chunk_id,
                    via="name-match", score=1.0))
                matched = True
        if not matched:
            for chunk in chunks:
                score = similarity(
                    section.content,
                    f"{chunk.name} {chunk.signature} {chunk.docstring}")
                if score >= similarity_threshold:
                    graph.links.append(Link(
                        section_id=section.section_id, chunk_id=chunk.chunk_id,
                        via="similarity", score=round(score, 3)))
    # dedupe
    seen: set[tuple[str, str]] = set()
    unique: list[Link] = []
    for link in graph.links:
        key = (link.section_id, link.chunk_id)
        if key not in seen:
            seen.add(key)
            unique.append(link)
    graph.links = unique
    return graph
