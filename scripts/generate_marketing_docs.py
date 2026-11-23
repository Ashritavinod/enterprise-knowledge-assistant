"""Generate the Honeycrumb Bakehouse marketing PDFs into data/policies/.

Usage (from the repository root):
    python scripts/generate_marketing_docs.py

Content lives in scripts/marketing_docs_content.py. The FAISS index rebuilds
automatically on the next backend start because the PDF text changes.
"""

import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from marketing_docs_content import COMPANY, DOCUMENTS  # noqa: E402

OUTPUT_DIRECTORY = Path(__file__).resolve().parents[1] / "data" / "policies"

CSS = """
body { font-family: sans-serif; font-size: 10.5pt; line-height: 1.45; color: #4A2C2A; }
h1 { font-family: serif; font-size: 22pt; color: #4A2C2A; margin-bottom: 2pt; }
h2 { font-family: serif; font-size: 14pt; color: #C77A06; margin-top: 14pt; margin-bottom: 4pt; }
h3 { font-size: 11pt; color: #E8456B; margin-top: 8pt; margin-bottom: 2pt; }
p { margin-top: 0; margin-bottom: 6pt; }
p.sub { color: #8A6B5A; font-style: italic; margin-bottom: 10pt; }
ul { margin-top: 0; margin-bottom: 6pt; }
li { margin-bottom: 3pt; }
table { border-collapse: collapse; width: 100%; margin-bottom: 8pt; }
th { border-bottom: 2px solid #F5A623; color: #C77A06; text-align: left; padding: 4pt; font-size: 9.5pt; }
td { border-bottom: 1px solid #EED9C4; padding: 4pt; font-size: 9.5pt; vertical-align: top; }
table.meta td { border-bottom: 1px solid #F3E6D8; }
"""

PAGE = pymupdf.paper_rect("letter")
CONTENT = PAGE + (54, 64, -54, -54)


def _stamp_pages(path: Path, title: str) -> None:
    """Add a header band and page-number footer to every page."""
    document = pymupdf.open(path)
    for number, page in enumerate(document, start=1):
        page.wrap_contents()
        page.draw_rect(pymupdf.Rect(0, 0, PAGE.width, 8), color=None, fill=(0.96, 0.65, 0.14))
        page.insert_text((54, 34), f"{COMPANY} · {title}", fontsize=8, color=(0.54, 0.42, 0.35))
        page.insert_text(
            (PAGE.width - 110, PAGE.height - 28),
            f"Page {number} of {document.page_count}",
            fontsize=8,
            color=(0.54, 0.42, 0.35),
        )
    document.saveIncr()
    document.close()


def render(name: str, html: str) -> Path:
    path = OUTPUT_DIRECTORY / name
    story = pymupdf.Story(html=html, user_css=CSS)
    writer = pymupdf.DocumentWriter(str(path))
    more = True
    while more:
        device = writer.begin_page(PAGE)
        more, _ = story.place(CONTENT)
        story.draw(device)
        writer.end_page()
    writer.close()
    title = name.removesuffix(".pdf")
    _stamp_pages(path, title)
    return path


def main() -> None:
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    for name, html in DOCUMENTS.items():
        path = render(name, html)
        pages = pymupdf.open(path).page_count
        print(f"Wrote {path.relative_to(OUTPUT_DIRECTORY.parents[1])} ({pages} pages)")


if __name__ == "__main__":
    main()
