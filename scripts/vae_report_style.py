"""
Styles PDF partagés pour les rapports VAE (ReportLab).
Couleurs, styles de paragraphe, tables et pied de page alignés sur rapport_final_vae.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ─── Palette ────────────────────────────────────────────────────────────────
NAVY = colors.HexColor("#1C2B4A")
BLUE = colors.HexColor("#1E5FA8")
GREEN = colors.HexColor("#1F7A54")
AMBER = colors.HexColor("#C77800")
RED = colors.HexColor("#C62828")
TEAL = colors.HexColor("#00838F")
GRAY_M = colors.HexColor("#6B7280")
GRAY_L = colors.HexColor("#F3F3F1")
WHITE = colors.HexColor("#FFFFFF")
BLUE_LT = colors.HexColor("#EBF2FA")
GREEN_LT = colors.HexColor("#E8F5F0")
AMBER_LT = colors.HexColor("#FDF3E3")
RED_LT = colors.HexColor("#FAEAEA")
TEAL_LT = colors.HexColor("#E0F5F9")

# Sans '#' pour openpyxl PatternFill
GREEN_LT_XL = "E8F5F0"
AMBER_LT_XL = "FDF3E3"
RED_LT_XL = "FAEAEA"

# ─── Mise en page ───────────────────────────────────────────────────────────
PAGE_WIDTH, PAGE_HEIGHT = A4
LEFT_MARGIN = RIGHT_MARGIN = 20 * mm
TOP_MARGIN = 18 * mm
BOTTOM_MARGIN = 16 * mm + 14 * mm
CONTENT_WIDTH = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN

_BASE = getSampleStyleSheet()

P_BODY = ParagraphStyle(
    "VAE_BODY",
    parent=_BASE["Normal"],
    fontName="Helvetica",
    fontSize=9.5,
    leading=15,
    textColor=colors.black,
    alignment=TA_LEFT,
)
P_JUST = ParagraphStyle(
    "VAE_JUST",
    parent=P_BODY,
    alignment=TA_JUSTIFY,
)
P_INS = ParagraphStyle(
    "VAE_INS",
    parent=P_BODY,
    fontSize=9.5,
    leading=14,
)
P_H1 = ParagraphStyle(
    "VAE_H1",
    parent=_BASE["Heading1"],
    fontName="Helvetica-Bold",
    fontSize=11,
    leading=14,
    textColor=NAVY,
    spaceBefore=6,
    spaceAfter=4,
)
P_SEC = ParagraphStyle(
    "VAE_SEC",
    parent=_BASE["Normal"],
    fontName="Helvetica-Bold",
    fontSize=9,
    leading=12,
    textColor=BLUE,
    spaceBefore=4,
    spaceAfter=2,
)
P_TH = ParagraphStyle(
    "VAE_TH",
    parent=_BASE["Normal"],
    fontName="Helvetica-Bold",
    fontSize=8,
    leading=10,
    textColor=WHITE,
    alignment=TA_CENTER,
)
P_TD = ParagraphStyle(
    "VAE_TD",
    parent=_BASE["Normal"],
    fontName="Helvetica",
    fontSize=8.5,
    leading=11,
    textColor=colors.black,
    alignment=TA_LEFT,
)
P_TD_CENTER = ParagraphStyle(
    "VAE_TD_C",
    parent=P_TD,
    alignment=TA_CENTER,
)
P_TD_RIGHT = ParagraphStyle(
    "VAE_TD_R",
    parent=P_TD,
    alignment=TA_RIGHT,
)
P_SMALL = ParagraphStyle(
    "VAE_SMALL",
    parent=_BASE["Normal"],
    fontName="Helvetica",
    fontSize=8,
    leading=11,
    textColor=GRAY_M,
)
P_TOC = ParagraphStyle(
    "VAE_TOC",
    parent=P_BODY,
    fontSize=9,
    leading=13,
    leftIndent=8,
)
P_ALERT_BODY = ParagraphStyle(
    "VAE_ALERT",
    parent=P_BODY,
    fontSize=9.5,
    leading=14,
)
P_COVER_TITLE = ParagraphStyle(
    "VAE_COVER_T",
    parent=_BASE["Normal"],
    fontName="Helvetica-Bold",
    fontSize=14,
    leading=17,
    textColor=WHITE,
)
P_COVER_SUB = ParagraphStyle(
    "VAE_COVER_S",
    parent=_BASE["Normal"],
    fontName="Helvetica",
    fontSize=10,
    leading=13,
    textColor=colors.HexColor("#AACCEE"),
)


def pdf_escape(s: str) -> str:
    """Échappe le XML ReportLab et degrade quelques glyphes hors Helvetica WinAnsi."""
    t = (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("✓ ", "")
        .replace("✓", "")
        .replace("✗ ", "X ")
        .replace("✗", "X ")
        .replace("⚠ ", "! ")
        .replace("⚠", "! ")
    )
    return t


def pdf_xml_fragment(s: str) -> str:
    """Échappe &, <, > pour un fragment inséré dans un paragraphe ReportLab qui utilise déjà des balises (<b>, …)."""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def HR() -> Table:
    return Table(
        [[""]],
        colWidths=[CONTENT_WIDTH],
        rowHeights=[2],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        ),
    )


def SEC(story: list, label: str) -> None:
    story.append(Spacer(1, 6))
    story.append(Paragraph(pdf_escape(label.upper()), P_SEC))


def H1(story: list, text: str) -> None:
    story.append(Spacer(1, 8))
    story.append(Paragraph(pdf_escape(text), P_H1))
    story.append(Spacer(1, 2))
    story.append(HR())
    story.append(Spacer(1, 8))


def _align_to_ta(align: str) -> int:
    a = (align or "LEFT").upper()
    if a in ("C", "CENTER"):
        return TA_CENTER
    if a in ("R", "RIGHT"):
        return TA_RIGHT
    if a in ("J", "JUST", "JUSTIFY"):
        return TA_JUSTIFY
    return TA_LEFT


def td(
    txt: str,
    bold: bool = False,
    color: colors.Color | None = None,
    align: str = "LEFT",
) -> Paragraph:
    raw = pdf_escape(str(txt))
    if bold:
        raw = f"<b>{raw}</b>"
    if color is not None:
        hx = color.hexval() if hasattr(color, "hexval") else str(color)
        raw = f'<font color="{hx}">{raw}</font>'
    st = ParagraphStyle(
        "TD_CELL",
        parent=P_TD,
        alignment=_align_to_ta(align),
        fontName="Helvetica-Bold" if bold else "Helvetica",
    )
    return Paragraph(raw, st)


def box_info(
    para: Paragraph,
    bg: colors.Color = BLUE_LT,
    border_color: colors.Color = BLUE,
) -> Table:
    t = Table([[para]], colWidths=[CONTENT_WIDTH])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), bg),
                ("BOX", (0, 0), (-1, -1), 1, border_color),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return t


def table_standard(
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    col_widths: Sequence[float],
    *,
    row_fills: Sequence[colors.Color | None] | None = None,
    repeat_rows: int = 1,
) -> Table:
    header_cells = [Paragraph(f"<b>{pdf_escape(h)}</b>", P_TH) for h in headers]
    data_rows: list[list[Paragraph]] = []
    for row in rows:
        data_rows.append([Paragraph(pdf_escape(str(c)), P_TD) for c in row])

    data = [header_cells, *data_rows]
    t = Table(data, colWidths=list(col_widths), repeatRows=repeat_rows)
    style_cmds: list[tuple] = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.25, GRAY_M),
    ]
    n_data = len(data_rows)
    for i in range(n_data):
        ri = i + 1
        if row_fills is not None:
            fill_i = row_fills[i] if i < len(row_fills) else None
            if fill_i is not None:
                style_cmds.append(("BACKGROUND", (0, ri), (-1, ri), fill_i))
            else:
                bg = WHITE if i % 2 == 0 else GRAY_L
                style_cmds.append(("BACKGROUND", (0, ri), (-1, ri), bg))
        else:
            bg = WHITE if i % 2 == 0 else GRAY_L
            style_cmds.append(("BACKGROUND", (0, ri), (-1, ri), bg))
    t.setStyle(TableStyle(style_cmds))
    return t


def kpi_block(items: Sequence[tuple[str, str, colors.Color | None]]) -> Table:
    """items : jusqu'à 4 tuples (label, valeur_str, couleur optionnelle pour la valeur)."""
    cells = []
    for label, val, col in list(items)[:4]:
        hx = ""
        if col is not None:
            hx = col.hexval() if hasattr(col, "hexval") else str(col)
            val_xml = f'<font color="{hx}"><b>{pdf_escape(val)}</b></font>'
        else:
            val_xml = f"<b>{pdf_escape(val)}</b>"
        p = Paragraph(f"{pdf_escape(label)}<br/>{val_xml}", P_SMALL)
        cells.append(p)
    while len(cells) < 4:
        cells.append(Paragraph("", P_SMALL))
    w = CONTENT_WIDTH / 4
    t = Table([cells], colWidths=[w, w, w, w])
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("BOX", (0, 0), (-1, -1), 0.5, GRAY_M),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, GRAY_L),
                ("BACKGROUND", (0, 0), (-1, -1), BLUE_LT),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return t


def cover_banner(title: str, subtitle: str) -> Table:
    pt = Paragraph(f"<b>{pdf_escape(title)}</b>", P_COVER_TITLE)
    ps = Paragraph(f"<font color='#AACCEE'>{pdf_escape(subtitle)}</font>", P_COVER_SUB)
    tbl = Table([[pt], [ps]], colWidths=[CONTENT_WIDTH])
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 14),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    return tbl


def add_footer(canvas: Canvas, doc: SimpleDocTemplate, firm_code: str, left_text: str) -> None:
    del firm_code  # API conforme au contrat projet ; le texte gauche est explicite.
    canvas.saveState()
    w, _h = PAGE_WIDTH, PAGE_HEIGHT
    canvas.setStrokeColor(NAVY)
    canvas.setLineWidth(1)
    y_line = 6 * mm
    canvas.line(LEFT_MARGIN, y_line, w - RIGHT_MARGIN, y_line)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GRAY_M)
    y_txt = 10 * mm
    canvas.drawString(LEFT_MARGIN, y_txt, str(left_text))
    page_txt = f"Page {doc.page}"
    tw = canvas.stringWidth(page_txt, "Helvetica", 8)
    canvas.drawRightString(w - RIGHT_MARGIN, y_txt, page_txt)
    canvas.restoreState()


def build_doc(
    filepath: str | Path,
    story: list,
    firm_code: str = "XXX",
    left_text: str = "Simulation marché VAE — Usage interne",
) -> None:
    path = Path(filepath)
    if not path.is_absolute():
        path = Path.cwd() / path
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=LEFT_MARGIN,
        rightMargin=RIGHT_MARGIN,
        topMargin=TOP_MARGIN,
        bottomMargin=BOTTOM_MARGIN,
    )

    def _draw_footer(canvas: Canvas, doc_: SimpleDocTemplate) -> None:
        add_footer(canvas, doc_, firm_code, left_text)

    doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)


_LEVEL_STYLE: dict[str, tuple[colors.Color, colors.Color]] = {
    "ok": (GREEN_LT, GREEN),
    "warning": (AMBER_LT, AMBER),
    "critical": (RED_LT, RED),
    "info": (BLUE_LT, BLUE),
    "teal": (TEAL_LT, TEAL),
}


def alerte(texte: str, niveau: str) -> Table:
    bg, bd = _LEVEL_STYLE[niveau]
    return box_info(Paragraph(pdf_escape(texte), P_ALERT_BODY), bg=bg, border_color=bd)


def toc_block(items: Sequence[str]) -> list:
    """Une ligne par entrée dans un tableau à colonne unique (évite les artefacts de rendu dupliqués)."""
    out: list = [Spacer(1, 6)]
    data = [[Paragraph(f"{i}. {pdf_escape(title)}", P_TOC)] for i, title in enumerate(items, 1)]
    if not data:
        return out
    t = Table(data, colWidths=[CONTENT_WIDTH])
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    out.append(t)
    return out


__all__ = [
    "AMBER",
    "AMBER_LT",
    "AMBER_LT_XL",
    "BLUE",
    "BLUE_LT",
    "BOTTOM_MARGIN",
    "CONTENT_WIDTH",
    "GREEN",
    "GREEN_LT",
    "GREEN_LT_XL",
    "GRAY_L",
    "GRAY_M",
    "H1",
    "HR",
    "LEFT_MARGIN",
    "NAVY",
    "P_ALERT_BODY",
    "P_BODY",
    "P_COVER_SUB",
    "P_COVER_TITLE",
    "P_H1",
    "P_INS",
    "P_JUST",
    "P_SEC",
    "P_SMALL",
    "P_TD",
    "P_TD_CENTER",
    "P_TD_RIGHT",
    "P_TH",
    "P_TOC",
    "PAGE_HEIGHT",
    "PAGE_WIDTH",
    "RED",
    "RED_LT",
    "RED_LT_XL",
    "RIGHT_MARGIN",
    "SEC",
    "TEAL",
    "TEAL_LT",
    "TOP_MARGIN",
    "WHITE",
    "add_footer",
    "alerte",
    "box_info",
    "build_doc",
    "cover_banner",
    "kpi_block",
    "pdf_escape",
    "pdf_xml_fragment",
    "table_standard",
    "td",
    "toc_block",
    "PageBreak",
    "Paragraph",
    "Spacer",
    "KeepTogether",
]
