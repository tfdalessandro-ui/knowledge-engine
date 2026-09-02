"""One-time generator for P1's multi-format corpus additions (md/html/csv/
json/xml/docx/xlsx/pptx), proving the ingestion pipeline handles every
Docling-backed format end to end, not just the P0 seed corpus's plain .txt
files.

PDF is deliberately NOT generated here: Docling's PDF backend downloads
layout-detection + OCR model weights from HuggingFace/ModelScope on first
use (verified: ~30MB+ across several files), which would make a default
`python -m ingest.pipeline` run over data/corpus/ require network access.
See tests/ingest/test_parsers_pdf.py (network-gated, skipped by default) and
LOGBOOK for detail. PDF parsing itself is implemented in ingest/parsers.py
and works -- it's just not exercised by the default corpus/test run.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_DIR = REPO_ROOT / "data" / "corpus"


def write_markdown():
    path = CORPUS_DIR / "doc26_hnsw.md"
    if path.exists():
        return False
    path.write_text(
        "# HNSW\n\n"
        "Hierarchical Navigable Small World (HNSW) is a graph-based algorithm "
        "for approximate nearest-neighbor search over vector embeddings. It "
        "builds a multi-layer graph where higher layers have fewer, "
        "longer-range links, letting a search start coarse and refine down to "
        "the target layer -- giving sub-linear query time at the cost of exact "
        "recall. It is the index structure FAISS uses for the P2 hybrid "
        "search phase of this project.\n",
        encoding="utf-8",
    )
    return True


def write_html():
    path = CORPUS_DIR / "doc27_robots_protocol.html"
    if path.exists():
        return False
    path.write_text(
        "<html><head><title>Robots Exclusion Protocol</title></head><body>"
        "<h1>robots.txt</h1>"
        "<p>The Robots Exclusion Protocol lets a site publish a robots.txt file "
        "at its root telling well-behaved crawlers which paths they may or may "
        "not fetch, and at what crawl rate. It is advisory, not enforced -- a "
        "crawler has to choose to respect it, which is why a compliant crawler "
        "checks and caches robots.txt before fetching any other URL on a "
        "domain.</p>"
        "</body></html>\n",
        encoding="utf-8",
    )
    return True


def write_csv():
    path = CORPUS_DIR / "doc28_server_comparison.csv"
    if path.exists():
        return False
    path.write_text(
        "server,vcpu,vcpu_type,ram_gb,disk_gb,region\n"
        "sensalis-node,2,shared,15,-,LAN (dev)\n"
        "CX23,4,shared,16,160,Helsinki\n"
        "CCX23,4,dedicated,16,160,Helsinki\n",
        encoding="utf-8",
    )
    return True


def write_json():
    path = CORPUS_DIR / "doc29_project_manifest.json"
    if path.exists():
        return False
    import json

    path.write_text(
        json.dumps(
            {
                "project": "cpu-first-knowledge-engine",
                "phase": "P1",
                "components": ["docling", "tantivy", "fastapi", "sqlite"],
                "description": "Ingestion and BM25 MVP over local documents, with incremental re-indexing.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return True


def write_xml():
    path = CORPUS_DIR / "doc30_sitemap_structure.xml"
    if path.exists():
        return False
    path.write_text(
        "<?xml version='1.0' encoding='UTF-8'?>\n"
        "<sitemap>"
        "<entry><url>https://example.com/docs/bm25</url>"
        "<note>A sitemap XML file lists canonical URLs for a crawler to fetch, "
        "often with a last-modified date, so a crawler can prioritize changed "
        "pages instead of re-fetching an entire site.</note></entry>"
        "</sitemap>\n",
        encoding="utf-8",
    )
    return True


def write_docx():
    path = CORPUS_DIR / "doc31_docling_parsers.docx"
    if path.exists():
        return False
    from docx import Document as DocxDocument

    doc = DocxDocument()
    doc.add_heading("Docling parsers", level=1)
    doc.add_paragraph(
        "Docling is a single parsing library that converts many document "
        "formats -- PDF, DOCX, XLSX, PPTX, HTML, Markdown, CSV -- into one "
        "unified document model, which this project exports back to Markdown "
        "text before chunking. Using one library instead of a parser per "
        "format keeps the ingestion pipeline's chunking and indexing code "
        "format-agnostic."
    )
    doc.save(path)
    return True


def write_xlsx():
    path = CORPUS_DIR / "doc32_benchmark_results.xlsx"
    if path.exists():
        return False
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "results"
    ws.append(["metric", "value"])
    ws.append(["p50_latency_ms", 0.31])
    ws.append(["p95_latency_ms", 0.39])
    ws.append(["peak_rss_mb", 35.0])
    ws.append(["note", "Benchmark results are logged as p50/p95 latency and peak resident memory (RSS) for a sample operation, reused across every later phase of this project."])
    wb.save(path)
    return True


def write_pptx():
    path = CORPUS_DIR / "doc33_roadmap_overview.pptx"
    if path.exists():
        return False
    from pptx import Presentation

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "Knowledge engine roadmap"
    slide.placeholders[1].text = (
        "Eight phases, P0 through P7. P0 and P5 are hard gates: P0 builds the "
        "evaluation harness before anything it will measure exists, and P5 "
        "requires permission-aware retrieval before any enterprise source is "
        "indexed."
    )
    prs.save(path)
    return True


def main() -> int:
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    writers = [write_markdown, write_html, write_csv, write_json, write_xml, write_docx, write_xlsx, write_pptx]
    written = sum(1 for w in writers if w())
    print(f"wrote {written} new multi-format document(s) to {CORPUS_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
