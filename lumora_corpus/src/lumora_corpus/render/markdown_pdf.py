"""Render the corpus's Markdown subset to PDF with reportlab.

Supported: paragraphs before the title (printed as a small header line), headings (#, ##,
###), paragraphs with **bold** and *italic*, flat bullet and numbered lists, and pipe
tables. Anything else raises, so a template cannot silently lose content.

Output is byte-identical across runs: reportlab's invariant mode fixes the creation date
and document ID.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from io import BytesIO
from xml.sax.saxutils import escape

from markdown_it import MarkdownIt
from markdown_it.token import Token
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    Flowable,
    ListFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

INK = colors.HexColor("#1f2933")
MUTED = colors.HexColor("#616e7c")
ACCENT = colors.HexColor("#3e6b5a")
RULE = colors.HexColor("#c5cdd3")
HEADER_FILL = colors.HexColor("#e8eeeb")

BODY = ParagraphStyle(
    "body", fontName="Helvetica", fontSize=10.5, leading=15, textColor=INK, spaceAfter=7
)
STYLES: dict[str, ParagraphStyle] = {
    "header": ParagraphStyle(
        "header",
        parent=BODY,
        fontName="Helvetica-Oblique",
        fontSize=9,
        textColor=MUTED,
        alignment=TA_RIGHT,
        spaceAfter=2,
    ),
    "h1": ParagraphStyle(
        "h1",
        parent=BODY,
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=25,
        textColor=ACCENT,
        spaceBefore=4,
        spaceAfter=6,
    ),
    "h2": ParagraphStyle(
        "h2",
        parent=BODY,
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        textColor=ACCENT,
        spaceBefore=12,
        spaceAfter=5,
    ),
    "h3": ParagraphStyle(
        "h3", parent=BODY, fontName="Helvetica-Bold", fontSize=11, spaceBefore=6, spaceAfter=3
    ),
    "body": BODY,
    "cell": ParagraphStyle("cell", parent=BODY, fontSize=9.5, leading=12.5, spaceAfter=0),
    "head_cell": ParagraphStyle(
        "head_cell", parent=BODY, fontName="Helvetica-Bold", fontSize=9.5, leading=12.5
    ),
}
MARGIN = 20 * mm


@dataclass(frozen=True, slots=True)
class PdfMeta:
    title: str  # PDF metadata title
    footer: str  # printed at the bottom of every page, before the page number
    author: str = "Lumora Home"


def _inline(token: Token) -> str:
    """reportlab paragraph markup for an inline token."""
    out: list[str] = []
    for child in token.children or []:
        match child.type:
            case "text":
                out.append(escape(child.content))
            case "strong_open":
                out.append("<b>")
            case "strong_close":
                out.append("</b>")
            case "em_open":
                out.append("<i>")
            case "em_close":
                out.append("</i>")
            case "softbreak":
                out.append(" ")
            case "hardbreak":
                out.append("<br/>")
            case "code_inline":
                out.append(f'<font name="Courier">{escape(child.content)}</font>')
            case _:
                raise ValueError(f"Unsupported inline Markdown: {child.type}")
    return "".join(out)


def _take_until(tokens: list[Token], start: int, closing: str) -> tuple[list[Token], int]:
    """Tokens after `start` up to the matching `closing` token, and the index after it."""
    depth = 0
    opening = closing.replace("_close", "_open")
    for i in range(start + 1, len(tokens)):
        if tokens[i].type == opening:
            depth += 1
        elif tokens[i].type == closing:
            if depth == 0:
                return tokens[start + 1 : i], i + 1
            depth -= 1
    raise ValueError(f"No {closing} after token {start}")


def _list(tokens: list[Token], ordered: bool) -> ListFlowable:
    items: list[Flowable] = []
    for token in tokens:
        if token.type in ("bullet_list_open", "ordered_list_open"):
            raise ValueError("Nested lists are not supported")
        if token.type == "inline":
            items.append(Paragraph(_inline(token), STYLES["body"]))
    return ListFlowable(
        items,
        bulletType="1" if ordered else "bullet",
        start=None if ordered else "•",
        leftIndent=14,
        bulletFontName="Helvetica",
        bulletFontSize=10,
        bulletColor=INK,
    )


def _table(tokens: list[Token], available: float) -> Table:
    rows: list[list[str]] = []
    header_rows = 0
    in_head = False
    for token in tokens:
        if token.type == "thead_open":
            in_head = True
        elif token.type == "thead_close":
            in_head = False
        elif token.type == "tr_open":
            rows.append([])
            header_rows += in_head
        elif token.type == "inline":
            rows[-1].append(_inline(token))
    width = max(len(r) for r in rows)
    # Column widths follow the longest cell in each column, within limits.
    weights = [min(max(max(len(r[c]) for r in rows if c < len(r)), 8), 48) for c in range(width)]
    widths = [available * w / sum(weights) for w in weights]
    cells = [
        [
            Paragraph(cell, STYLES["head_cell"] if r < header_rows else STYLES["cell"])
            for cell in row
        ]
        for r, row in enumerate(rows)
    ]
    table = Table(cells, colWidths=widths, repeatRows=header_rows, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, RULE),
                ("BACKGROUND", (0, 0), (-1, header_rows - 1), HEADER_FILL),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _flowables(markdown: str, available: float) -> Iterator[Flowable]:
    tokens = MarkdownIt("commonmark").enable("table").parse(markdown)
    seen_title = False
    i = 0
    while i < len(tokens):
        token = tokens[i]
        match token.type:
            case "heading_open":
                seen_title = True
                yield Paragraph(_inline(tokens[i + 1]), STYLES[token.tag])
                i += 3
            case "paragraph_open":
                style = STYLES["body"] if seen_title else STYLES["header"]
                yield Paragraph(_inline(tokens[i + 1]), style)
                i += 3
            case "bullet_list_open" | "ordered_list_open":
                inner, i = _take_until(tokens, i, token.type.replace("_open", "_close"))
                yield _list(inner, ordered=token.type == "ordered_list_open")
                yield Spacer(1, 6)
            case "table_open":
                inner, i = _take_until(tokens, i, "table_close")
                yield _table(inner, available)
                yield Spacer(1, 8)
            case _:
                raise ValueError(f"Unsupported Markdown block: {token.type}")


def _footer(meta: PdfMeta) -> Callable[[Canvas, SimpleDocTemplate], None]:
    def draw(canvas: Canvas, doc: SimpleDocTemplate) -> None:
        canvas.saveState()
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, 14 * mm, A4[0] - MARGIN, 14 * mm)
        canvas.setFont("Helvetica", 8.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(MARGIN, 10 * mm, meta.footer)
        canvas.drawRightString(A4[0] - MARGIN, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    return draw


def render_pdf(markdown: str, meta: PdfMeta) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=18 * mm,
        bottomMargin=22 * mm,
        title=meta.title,
        author=meta.author,
        creator=meta.author,
        invariant=1,
    )
    footer = _footer(meta)
    doc.build(list(_flowables(markdown, doc.width)), onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
