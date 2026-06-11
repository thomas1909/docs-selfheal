"""Split markdown docs into sections by heading and extract code references."""

from __future__ import annotations

import re
from pathlib import Path

from .schemas import DocSection

_CODE_REF = re.compile(r"`([A-Za-z_][A-Za-z0-9_.]*)\(?\)?`")


def parse_markdown(text: str, file: str) -> list[DocSection]:
    sections: list[DocSection] = []
    heading_stack: list[str] = []
    current_lines: list[str] = []
    current_path = "(intro)"

    def flush() -> None:
        content = "\n".join(current_lines).strip()
        if not content:
            return
        refs = sorted({m.group(1) for m in _CODE_REF.finditer(content)})
        slug = re.sub(r"[^a-z0-9>]+", "-", current_path.lower()).strip("-")
        sections.append(DocSection(
            section_id=f"{file}#{slug}",
            file=file,
            heading_path=current_path,
            content=content,
            code_refs=refs,
        ))

    for line in text.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            flush()
            current_lines = []
            level = len(m.group(1))
            heading_stack = heading_stack[: level - 1]
            heading_stack.append(m.group(2).strip())
            current_path = " > ".join(heading_stack)
        else:
            current_lines.append(line)
    flush()
    return sections


def parse_docs_dir(root: Path) -> list[DocSection]:
    sections: list[DocSection] = []
    for path in sorted(Path(root).rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        sections.extend(parse_markdown(path.read_text(encoding="utf-8"), rel))
    return sections
