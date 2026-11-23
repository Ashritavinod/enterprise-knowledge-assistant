"""Helpers for loading policy PDFs as structure-aware text.

Each page becomes one Document whose text keeps the PDF's layout structure so
the chunker can split on real boundaries instead of character counts:

* headings are marked like Markdown: "# " (title), "## " (section) and
  "### " (subsection), detected from font size and weight;
* paragraphs, bullet items and table rows are separated by blank lines;
* table cells on the same row are joined with " | ";
* running page headers and footers (page numbers etc.) are dropped.
"""

import logging
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pymupdf
from langchain_core.documents import Document

logger = logging.getLogger(__name__)
POLICIES_DIRECTORY = Path(__file__).resolve().parents[2] / "data" / "policies"

# Typographic ligatures (ﬀ, ﬁ, ﬂ, ﬃ, ﬄ, ﬅ, ﬆ) that PDF text extraction can
# return as single characters; expand them so words like "staff" match searches.
_LIGATURES = str.maketrans(
    {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi",
     "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st"}
)
_BULLET = re.compile(r"^[•●▪◦‣∙·-]\s+")

# Layout heuristics (in PDF points / multiples of body font size).
MARGIN_BAND = 45  # running headers/footers live within this distance of the edge
MARGIN_TEXT_MAX = 100  # ...and are short
CELL_GAP = 6  # horizontal gap (word spaces are ~2.5pt) between spans that indicates a new table cell
TITLE_SCALE = 1.8  # font size relative to body text for "# " titles
SECTION_SCALE = 1.2  # ... for "## " sections
HEADING_MAX_CHARS = 90


def normalize_text(text: str) -> str:
    return text.translate(_LIGATURES)


@dataclass
class _Block:
    text: str
    top: float
    bottom: float
    left: float
    size: float
    bold: bool
    line_count: int


def _span_is_bold(span: dict) -> bool:
    return bool(span["flags"] & 16) or "bold" in span["font"].lower()


def _block_text(raw_block: dict) -> str:
    """Join a block's spans in reading order.

    Spans on the same visual row are joined directly, or with " | " when a wide
    horizontal gap separates them (table cells); rows are joined with spaces.
    """
    spans = sorted(
        (s for line in raw_block["lines"] for s in line["spans"] if s["text"].strip()),
        key=lambda s: (s["bbox"][1], s["bbox"][0]),
    )
    rows: list[list[dict]] = []
    for span in spans:
        y0, y1 = span["bbox"][1], span["bbox"][3]
        if rows:
            row_y0 = min(s["bbox"][1] for s in rows[-1])
            row_y1 = max(s["bbox"][3] for s in rows[-1])
            if min(y1, row_y1) - max(y0, row_y0) > 0.5 * (y1 - y0):
                rows[-1].append(span)
                continue
        rows.append([span])

    row_texts: list[str] = []
    for row in rows:
        parts: list[str] = []
        previous_end: float | None = None
        for span in sorted(row, key=lambda s: s["bbox"][0]):
            if previous_end is not None:
                gap = span["bbox"][0] - previous_end
                parts.append(" | " if gap > CELL_GAP else ("" if gap < 1 else " "))
            parts.append(span["text"])
            previous_end = span["bbox"][2]
        row_texts.append("".join(parts))
    return re.sub(r"\s+", " ", " ".join(row_texts)).strip()


def _page_blocks(page: pymupdf.Page) -> list[_Block]:
    blocks: list[_Block] = []
    height = page.rect.height
    for raw in page.get_text("dict")["blocks"]:
        if raw.get("type") != 0:
            continue
        spans = [s for line in raw["lines"] for s in line["spans"] if s["text"].strip()]
        if not spans:
            continue
        text = normalize_text(_block_text(raw))
        x0, y0, _, y1 = raw["bbox"]
        in_margin = y1 < MARGIN_BAND or y0 > height - MARGIN_BAND
        if not text or (in_margin and len(text) <= MARGIN_TEXT_MAX):
            continue
        blocks.append(
            _Block(
                text=text,
                top=y0,
                bottom=y1,
                left=x0,
                size=max(s["size"] for s in spans),
                bold=all(_span_is_bold(s) for s in spans),
                line_count=len(raw["lines"]),
            )
        )
    return blocks


def _merge_rows(blocks: list[_Block]) -> list[list[_Block]]:
    """Group side-by-side blocks (table cells) that share a row."""
    rows: list[list[_Block]] = []
    for block in sorted(blocks, key=lambda b: (round(b.top), b.left)):
        if rows:
            row = rows[-1]
            row_top = min(b.top for b in row)
            row_bottom = max(b.bottom for b in row)
            overlap = min(row_bottom, block.bottom) - max(row_top, block.top)
            if overlap > 0.5 * min(block.bottom - block.top, row_bottom - row_top):
                row.append(block)
                continue
        rows.append([block])
    return rows


def _body_font_size(pages: list[list[_Block]]) -> float:
    sizes: Counter[float] = Counter()
    for blocks in pages:
        for block in blocks:
            sizes[round(block.size, 1)] += len(block.text)
    return sizes.most_common(1)[0][0] if sizes else 10.0


def _render_row(row: list[_Block], body_size: float) -> str:
    if len(row) > 1:
        return " | ".join(b.text for b in sorted(row, key=lambda b: b.left))
    block = row[0]
    text = _BULLET.sub("• ", block.text)
    is_heading_shape = (
        len(text) <= HEADING_MAX_CHARS and block.line_count <= 2 and " | " not in text
    )
    if is_heading_shape and block.size >= body_size * TITLE_SCALE:
        return f"# {text}"
    if is_heading_shape and block.size >= body_size * SECTION_SCALE:
        return f"## {text}"
    if is_heading_shape and block.bold and block.size >= body_size and not text.startswith("•"):
        return f"### {text}"
    return text


def extract_structured_pages(pdf_path: Path) -> list[str]:
    """Return one structure-marked text string per page of the PDF."""
    with pymupdf.open(pdf_path) as pdf:
        pages = [_page_blocks(page) for page in pdf]
    body_size = _body_font_size(pages)
    return [
        "\n\n".join(_render_row(row, body_size) for row in _merge_rows(blocks))
        for blocks in pages
    ]


def find_pdf_files() -> list[Path]:
    """Return all PDF files under the policies directory in stable order."""
    return sorted(
        (
            path
            for path in POLICIES_DIRECTORY.rglob("*")
            if path.is_file() and path.suffix.lower() == ".pdf"
        ),
        key=lambda path: str(path).casefold(),
    )


def load_documents() -> list[Document]:
    """Load every PDF under the policies directory, skipping unreadable files."""
    pdf_files = find_pdf_files()
    logger.info(
        "Discovered %d PDF file(s) in %s",
        len(pdf_files),
        POLICIES_DIRECTORY,
    )

    documents: list[Document] = []
    loaded_files = 0
    failures = 0

    for pdf_path in pdf_files:
        logger.info("Found PDF: %s", pdf_path.name)
        try:
            pages = extract_structured_pages(pdf_path)
        except Exception:
            failures += 1
            logger.exception("Failed to load PDF: %s", pdf_path)
            continue

        for page_index, text in enumerate(pages):
            if not text.strip():
                continue
            documents.append(
                Document(
                    page_content=text,
                    metadata={
                        "source": str(pdf_path),
                        "page": page_index,
                        "page_number": page_index + 1,
                        "total_pages": len(pages),
                    },
                )
            )
        loaded_files += 1

    logger.info(
        "Loaded %d page(s) from %d PDF file(s); %d file(s) failed",
        len(documents),
        loaded_files,
        failures,
    )
    return documents
