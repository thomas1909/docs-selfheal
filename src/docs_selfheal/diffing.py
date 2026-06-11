"""Detect meaningful code changes between two snapshots of the codebase.

Comment-only / formatting churn is invisible here by construction: chunks are
compared on ast-derived signature and body hash, not on raw text.
"""

from __future__ import annotations

from .schemas import ChangeType, CodeChange, CodeChunk


def diff_chunks(old: list[CodeChunk], new: list[CodeChunk]) -> list[CodeChange]:
    old_by_id = {c.chunk_id: c for c in old}
    new_by_id = {c.chunk_id: c for c in new}
    changes: list[CodeChange] = []

    for chunk_id, old_chunk in old_by_id.items():
        new_chunk = new_by_id.get(chunk_id)
        if new_chunk is None:
            changes.append(CodeChange(
                chunk_id=chunk_id, change_type=ChangeType.removed, old=old_chunk))
        elif old_chunk.signature != new_chunk.signature:
            changes.append(CodeChange(
                chunk_id=chunk_id, change_type=ChangeType.signature_changed,
                old=old_chunk, new=new_chunk))
        elif old_chunk.body_hash != new_chunk.body_hash:
            changes.append(CodeChange(
                chunk_id=chunk_id, change_type=ChangeType.body_changed,
                old=old_chunk, new=new_chunk))

    for chunk_id, new_chunk in new_by_id.items():
        if chunk_id not in old_by_id:
            changes.append(CodeChange(
                chunk_id=chunk_id, change_type=ChangeType.added, new=new_chunk))
    return changes


def meaningful_changes(changes: list[CodeChange]) -> list[CodeChange]:
    """Docs only care about API surface: signature changes, additions, removals.
    Body-only changes are kept with lower priority (behavior may have changed)."""
    priority = {
        ChangeType.removed: 0,
        ChangeType.signature_changed: 1,
        ChangeType.added: 2,
        ChangeType.body_changed: 3,
    }
    return sorted(changes, key=lambda c: priority[c.change_type])
