"""Render the golden corpus to PDFs.

PDFs are build artifacts, not sources — the text in `corpus.py` is the reviewable
version, and the generated files are git-ignored. Regenerating is idempotent, so
the eval can rebuild them on every run without churn.
"""

from __future__ import annotations

from pathlib import Path

from agent.evals import BUILD_DIR
from agent.evals.corpus import CONTRACTS, FOOTER, pages_for

LINE_HEIGHT = 14.5
BODY_SIZE = 10.5
LEFT_MARGIN = 64


def build_contract(name: str, out_dir: Path = BUILD_DIR) -> Path:
    """Render one contract to PDF and return its path."""
    from reportlab.lib.pagesizes import LETTER
    from reportlab.pdfgen import canvas

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.pdf"

    width, height = LETTER
    pdf = canvas.Canvas(str(path), pagesize=LETTER)

    for page_number, lines in enumerate(pages_for(name), start=1):
        pdf.setFont("Helvetica", BODY_SIZE)
        y = height - 64
        for line in lines:
            if y < 72:  # overflow guard: keep text off the footer
                break
            pdf.drawString(LEFT_MARGIN, y, line[:96])
            y -= LINE_HEIGHT

        # A running footer on every page, plus a bare page number. Both are the
        # kind of noise the parser is expected to strip.
        pdf.setFont("Helvetica", 7.5)
        pdf.drawString(LEFT_MARGIN, 44, FOOTER)
        pdf.drawCentredString(width / 2, 30, str(page_number))
        pdf.showPage()

    pdf.save()
    return path


def build_all(out_dir: Path = BUILD_DIR) -> dict[str, Path]:
    """Render every contract in the corpus."""
    return {name: build_contract(name, out_dir) for name in CONTRACTS}


if __name__ == "__main__":
    for name, path in build_all().items():
        print(f"{name:20s} -> {path}  ({path.stat().st_size:,} bytes)")
