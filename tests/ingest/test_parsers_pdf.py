"""PDF parsing test -- gated behind KE_ENABLE_PDF_TESTS=1 because Docling's
PDF backend downloads OCR/layout model weights from HuggingFace/ModelScope on
first use. Keeping this out of the default `pytest -q` run is what lets
HELP.md still claim the default suite runs fully offline; run this explicitly
when you want to verify PDF parsing (first run needs network, later runs use
the local HuggingFace cache).
"""
import os

import pytest

from ingest.parsers import parse_to_text

pytestmark = pytest.mark.skipif(
    os.environ.get("KE_ENABLE_PDF_TESTS") != "1",
    reason="PDF parsing downloads ML models on first use; set KE_ENABLE_PDF_TESTS=1 to run this test",
)


def test_pdf(tmp_path):
    from reportlab.pdfgen import canvas

    path = tmp_path / "a.pdf"
    c = canvas.Canvas(str(path))
    c.drawString(100, 750, "MarkerPDFValue")
    c.save()
    assert "MarkerPDFValue" in parse_to_text(path)
