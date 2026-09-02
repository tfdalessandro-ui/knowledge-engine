"""Format-specific text extraction. One entry point, `parse_to_text(path)`,
returns plain text for any supported extension.

Docling (the P1 tech choice) handles the document formats it's built for --
PDF/DOCX/XLSX/PPTX/HTML/MD/CSV. TXT/JSON/XML are structurally trivial and get
lightweight dedicated readers instead of going through Docling's document
model, which is built around richly laid-out documents, not flat text/data
files.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable

DOCLING_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".pptx", ".html", ".htm", ".md", ".csv"}
SIMPLE_EXTENSIONS = {".txt", ".json", ".xml"}
SUPPORTED_EXTENSIONS = DOCLING_EXTENSIONS | SIMPLE_EXTENSIONS

_docling_converter = None  # lazy singleton; Docling's converter loads model backends on construction


def _get_docling_converter():
    global _docling_converter
    if _docling_converter is None:
        from docling.document_converter import DocumentConverter

        _docling_converter = DocumentConverter()
    return _docling_converter


def _parse_with_docling(path: Path) -> str:
    result = _get_docling_converter().convert(str(path))
    return result.document.export_to_markdown()


def _parse_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _parse_json(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    return json.dumps(data, indent=2, ensure_ascii=False)


def _iter_xml_text(elem: ET.Element):
    if elem.text and elem.text.strip():
        yield elem.text.strip()
    for child in elem:
        yield from _iter_xml_text(child)
        if child.tail and child.tail.strip():
            yield child.tail.strip()


def _parse_xml(path: Path) -> str:
    tree = ET.parse(path)
    return "\n".join(_iter_xml_text(tree.getroot()))


_SIMPLE_PARSERS: dict[str, Callable[[Path], str]] = {
    ".txt": _parse_txt,
    ".json": _parse_json,
    ".xml": _parse_xml,
}


def parse_to_text(path: Path) -> str:
    """Extract plain text from a supported file. Raises ValueError for an
    unsupported extension so the pipeline can report it explicitly rather
    than silently skipping a file."""
    ext = path.suffix.lower()
    if ext in DOCLING_EXTENSIONS:
        return _parse_with_docling(path)
    if ext in _SIMPLE_PARSERS:
        return _SIMPLE_PARSERS[ext](path)
    raise ValueError(f"unsupported extension {ext!r} for {path}")
