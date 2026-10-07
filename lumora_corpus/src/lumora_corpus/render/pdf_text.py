"""Reading text back out of generated PDFs (manifest page lookup and tests)."""

import pypdfium2 as pdfium


def page_texts(pdf: bytes) -> list[str]:
    """The text layer of each page; an empty string for a page without one."""
    doc = pdfium.PdfDocument(pdf)
    try:
        texts: list[str] = []
        for index in range(len(doc)):
            page = doc[index]
            textpage = page.get_textpage()
            texts.append(textpage.get_text_range())
            textpage.close()
            page.close()
        return texts
    finally:
        doc.close()


def normalise(text: str) -> str:
    """Collapse whitespace, so line wrapping in the PDF does not matter."""
    return " ".join(text.split())


def find_page(pages: list[str], text: str) -> int | None:
    """The 1-based page whose text contains `text`, or None."""
    needle = normalise(text)
    for number, page in enumerate(pages, start=1):
        if needle in normalise(page):
            return number
    return None
