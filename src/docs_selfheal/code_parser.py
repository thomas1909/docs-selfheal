"""Parse a Python codebase into semantic chunks via ast (no regex on code)."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from .schemas import ChunkKind, CodeChunk


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = []
    posargs = node.args.posonlyargs + node.args.args
    defaults: list[ast.expr | None] = [None] * (len(posargs) - len(node.args.defaults))
    defaults += list(node.args.defaults)
    for arg, default in zip(posargs, defaults):
        part = arg.arg
        if arg.annotation is not None:
            part += f": {ast.unparse(arg.annotation)}"
        if default is not None:
            part += f" = {ast.unparse(default)}"
        args.append(part)
    if node.args.vararg:
        args.append("*" + node.args.vararg.arg)
    for kwarg, kwdefault in zip(node.args.kwonlyargs, node.args.kw_defaults):
        part = kwarg.arg
        if kwarg.annotation is not None:
            part += f": {ast.unparse(kwarg.annotation)}"
        if kwdefault is not None:
            part += f" = {ast.unparse(kwdefault)}"
        args.append(part)
    if node.args.kwarg:
        args.append("**" + node.args.kwarg.arg)
    ret = f" -> {ast.unparse(node.returns)}" if node.returns is not None else ""
    return f"{node.name}({', '.join(args)}){ret}"


def _body_hash(node: ast.AST) -> str:
    return hashlib.sha1(ast.dump(node).encode()).hexdigest()[:12]


def parse_source(source: str, file: str) -> list[CodeChunk]:
    tree = ast.parse(source)
    chunks: list[CodeChunk] = []

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualname = f"{prefix}{child.name}"
                chunks.append(CodeChunk(
                    chunk_id=f"{file}::{qualname}",
                    file=file,
                    name=child.name,
                    kind=ChunkKind.method if prefix else ChunkKind.function,
                    signature=_signature(child),
                    docstring=ast.get_docstring(child) or "",
                    body_hash=_body_hash(child),
                ))
            elif isinstance(child, ast.ClassDef):
                qualname = f"{prefix}{child.name}"
                chunks.append(CodeChunk(
                    chunk_id=f"{file}::{qualname}",
                    file=file,
                    name=child.name,
                    kind=ChunkKind.klass,
                    signature=f"class {child.name}",
                    docstring=ast.get_docstring(child) or "",
                    body_hash=_body_hash(child),
                ))
                visit(child, qualname + ".")

    visit(tree, "")
    return chunks


def parse_codebase(root: Path) -> list[CodeChunk]:
    chunks: list[CodeChunk] = []
    for path in sorted(Path(root).rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        if any(part.startswith(".") or part in ("__pycache__", "tests", ".venv")
               for part in path.relative_to(root).parts):
            continue
        try:
            chunks.extend(parse_source(path.read_text(encoding="utf-8"), rel))
        except SyntaxError:
            continue
    return chunks
