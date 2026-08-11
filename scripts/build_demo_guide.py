#!/usr/bin/env python3
"""Build the CourtEdge ProGear team demo guide as a styled Word document."""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_ROW_HEIGHT_RULE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "CourtEdge-ProGear-Team-Demo-Guide.md"
OUTPUT = ROOT / "docs" / "CourtEdge-ProGear-Team-Demo-Guide.docx"

BROWN = "4A2C1A"
ORANGE = "E65F1B"
ORANGE_LIGHT = "FFF2E8"
PURPLE = "6437E8"
BLUE = "2457D6"
INK = "172033"
MUTED = "536078"
PALE = "F6F8FC"
GREEN = "0F7B4D"


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=100, start=120, bottom=100, end=120) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for tag, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{tag}"))
        if node is None:
            node = OxmlElement(f"w:{tag}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_repeat_table_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    repeat = OxmlElement("w:tblHeader")
    repeat.set(qn("w:val"), "true")
    tr_pr.append(repeat)


def prevent_row_split(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    cannot_split = OxmlElement("w:cantSplit")
    tr_pr.append(cannot_split)


def add_page_number(paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = paragraph.add_run("Page ")
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor.from_string(MUTED)
    fld_char_1 = OxmlElement("w:fldChar")
    fld_char_1.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    fld_char_2 = OxmlElement("w:fldChar")
    fld_char_2.set(qn("w:fldCharType"), "end")
    run._r.extend((fld_char_1, instr, fld_char_2))


def add_hyperlink(paragraph, text: str, url: str, color=BLUE, underline=True):
    relationship = paragraph.part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), relationship)
    run = OxmlElement("w:r")
    run_props = OxmlElement("w:rPr")
    color_el = OxmlElement("w:color")
    color_el.set(qn("w:val"), color)
    run_props.append(color_el)
    if underline:
        underline_el = OxmlElement("w:u")
        underline_el.set(qn("w:val"), "single")
        run_props.append(underline_el)
    run.append(run_props)
    text_el = OxmlElement("w:t")
    text_el.text = text
    run.append(text_el)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)


INLINE_RE = re.compile(r"(\*\*.+?\*\*|`.+?`|https?://[^\s]+)")


def add_inline(paragraph, text: str) -> None:
    position = 0
    for match in INLINE_RE.finditer(text):
        if match.start() > position:
            paragraph.add_run(text[position:match.start()])
        token = match.group(0)
        if token.startswith("**"):
            run = paragraph.add_run(token[2:-2])
            run.bold = True
        elif token.startswith("`"):
            run = paragraph.add_run(token[1:-1])
            run.font.name = "Aptos Mono"
            run.font.size = Pt(9)
            run.font.color.rgb = RGBColor.from_string(PURPLE)
        else:
            trailing = ""
            while token and token[-1] in ".,)":
                trailing = token[-1] + trailing
                token = token[:-1]
            add_hyperlink(paragraph, token, token)
            if trailing:
                paragraph.add_run(trailing)
        position = match.end()
    if position < len(text):
        paragraph.add_run(text[position:])


def add_top_rule(document: Document) -> None:
    table = document.add_table(rows=1, cols=1)
    table.autofit = True
    cell = table.cell(0, 0)
    set_cell_shading(cell, ORANGE)
    set_cell_margins(cell, top=20, bottom=20)
    cell.paragraphs[0].add_run(" ")


def add_callout(document: Document, text: str, fill=ORANGE_LIGHT, accent=ORANGE) -> None:
    table = document.add_table(rows=1, cols=1)
    table.autofit = True
    cell = table.cell(0, 0)
    set_cell_shading(cell, fill)
    set_cell_margins(cell, top=140, start=170, bottom=140, end=170)
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    start = OxmlElement("w:start")
    start.set(qn("w:val"), "single")
    start.set(qn("w:sz"), "22")
    start.set(qn("w:color"), accent)
    borders.append(start)
    tc_pr.append(borders)
    paragraph = cell.paragraphs[0]
    paragraph.paragraph_format.space_after = Pt(0)
    add_inline(paragraph, text)


def add_markdown_table(document: Document, rows: list[list[str]]) -> None:
    table = document.add_table(rows=1, cols=len(rows[0]))
    table.style = "Table Grid"
    table.autofit = True
    header = table.rows[0]
    set_repeat_table_header(header)
    for index, value in enumerate(rows[0]):
        cell = header.cells[index]
        set_cell_shading(cell, BROWN)
        set_cell_margins(cell)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        paragraph = cell.paragraphs[0]
        add_inline(paragraph, value.strip())
        for run in paragraph.runs:
            run.bold = True
            run.font.color.rgb = RGBColor(255, 255, 255)
            run.font.size = Pt(9)
    for row_index, row_data in enumerate(rows[1:]):
        row = table.add_row()
        prevent_row_split(row)
        if row_index % 2:
            for cell in row.cells:
                set_cell_shading(cell, PALE)
        for index, value in enumerate(row_data):
            cell = row.cells[index]
            set_cell_margins(cell)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.space_after = Pt(0)
            add_inline(paragraph, value.strip())
            for run in paragraph.runs:
                run.font.size = Pt(8.5)
    document.add_paragraph().paragraph_format.space_after = Pt(0)


def add_screenshot(document: Document, alt: str, relative_path: str) -> None:
    path = SOURCE.parent / relative_path
    if not path.exists():
        raise FileNotFoundError(path)
    section = document.sections[-1]
    available_width = section.page_width - section.left_margin - section.right_margin
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.keep_with_next = True
    run = paragraph.add_run()
    run.add_picture(str(path), width=available_width)
    caption = document.add_paragraph(style="Caption")
    caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption.paragraph_format.space_after = Pt(8)
    caption.add_run(alt)
    if relative_path.endswith("09-sequence.png"):
        document.add_page_break()


def set_section_layout(section, landscape: bool) -> None:
    section.top_margin = Inches(0.55)
    section.bottom_margin = Inches(0.55)
    section.left_margin = Inches(0.65)
    section.right_margin = Inches(0.65)
    if landscape:
        section.orientation = WD_ORIENT.LANDSCAPE
        section.page_width = Inches(11)
        section.page_height = Inches(8.5)
    else:
        section.orientation = WD_ORIENT.PORTRAIT
        section.page_width = Inches(8.5)
        section.page_height = Inches(11)


def add_section(document: Document, landscape: bool) -> None:
    section = document.add_section(WD_SECTION.NEW_PAGE)
    set_section_layout(section, landscape)
    section.header.is_linked_to_previous = True
    section.footer.is_linked_to_previous = True


def add_cover(document: Document) -> None:
    add_top_rule(document)
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(44)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run("COURTEDGE PROGEAR")
    run.bold = True
    run.font.size = Pt(14)
    run.font.color.rgb = RGBColor.from_string(ORANGE)
    run.font.letter_spacing = Pt(1.5)

    title = document.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_before = Pt(8)
    title.paragraph_format.space_after = Pt(6)
    run = title.add_run("Team Demo Guide")
    run.bold = True
    run.font.size = Pt(32)
    run.font.color.rgb = RGBColor.from_string(INK)

    subtitle = document.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.paragraph_format.space_after = Pt(28)
    run = subtitle.add_run("Everyday access, governed agent identity, and optional FGA approval")
    run.font.size = Pt(14)
    run.font.color.rgb = RGBColor.from_string(MUTED)

    table = document.add_table(rows=3, cols=2)
    table.style = "Table Grid"
    table.autofit = False
    labels = ("Demo URL", "FGA video", "Updated")
    values = (
        "https://progear-sales-aiagent.vercel.app",
        "Paste the Google Drive link here",
        date.today().strftime("%B %-d, %Y"),
    )
    for index, (label, value) in enumerate(zip(labels, values)):
        left, right = table.rows[index].cells
        left.width = Inches(1.25)
        right.width = Inches(5.5)
        set_cell_shading(left, BROWN)
        set_cell_shading(right, "FFFFFF" if index != 1 else "FFF8DB")
        for cell in (left, right):
            set_cell_margins(cell, top=145, bottom=145)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        label_run = left.paragraphs[0].add_run(label)
        label_run.bold = True
        label_run.font.color.rgb = RGBColor(255, 255, 255)
        if index == 0:
            add_hyperlink(right.paragraphs[0], value, value)
        else:
            right.paragraphs[0].add_run(value)

    note = document.add_paragraph()
    note.alignment = WD_ALIGN_PARAGRAPH.CENTER
    note.paragraph_format.space_before = Pt(34)
    note.paragraph_format.space_after = Pt(0)
    run = note.add_run("Internal presenter guide • Passwords are managed separately")
    run.italic = True
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor.from_string(MUTED)

    document.add_page_break()


def configure_styles(document: Document) -> None:
    styles = document.styles
    normal = styles["Normal"]
    normal.font.name = "Aptos"
    normal.font.size = Pt(9.5)
    normal.font.color.rgb = RGBColor.from_string(INK)
    normal.paragraph_format.space_after = Pt(5)
    normal.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE

    for name, size, color in (
        ("Title", 32, INK),
        ("Heading 1", 20, BROWN),
        ("Heading 2", 14, ORANGE),
        ("Heading 3", 11, PURPLE),
    ):
        style = styles[name]
        style.font.name = "Aptos Display"
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)
        style.paragraph_format.keep_with_next = True
        style.paragraph_format.space_before = Pt(10)
        style.paragraph_format.space_after = Pt(5)

    caption = styles["Caption"]
    caption.font.name = "Aptos"
    caption.font.size = Pt(8)
    caption.font.italic = True
    caption.font.color.rgb = RGBColor.from_string(MUTED)

    if "Callout" not in styles:
        callout = styles.add_style("Callout", WD_STYLE_TYPE.PARAGRAPH)
        callout.base_style = styles["Normal"]
        callout.font.bold = True
        callout.font.color.rgb = RGBColor.from_string(BROWN)


def configure_headers(document: Document) -> None:
    section = document.sections[0]
    section.different_first_page_header_footer = True
    header = section.header
    paragraph = header.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = paragraph.add_run("CourtEdge ProGear  |  Team Demo Guide")
    run.bold = True
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor.from_string(BROWN)
    add_page_number(section.footer.paragraphs[0])


PAGE_BREAK_BEFORE = {
    "2. Sarah reads inventory",
    "3. Sarah tries to write",
    "4. Mike performs a normal write",
    "5. Mike tries 601 units in simple mode",
    "7. Walk through the sequence",
    "9. Explain the FGA policy",
    "10. Demonstrate Manager-to-VP approval",
    "11. Optional vacation demonstration",
    "End-of-demo reset checklist",
}


def parse_markdown(document: Document, lines: list[str]) -> None:
    # The cover already contains the URL, video placeholder, audience, and
    # credential handling note. Start the body at the actual story.
    index = lines.index("## The story in one minute")
    landscape = False
    while index < len(lines):
        raw = lines[index].rstrip()
        stripped = raw.strip()
        if not stripped:
            index += 1
            continue

        if stripped.startswith("| "):
            table_lines = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index].strip())
                index += 1
            rows = []
            for table_index, line in enumerate(table_lines):
                values = [item.strip() for item in line.strip("|").split("|")]
                if table_index == 1 and all(re.fullmatch(r":?-+:?", item) for item in values):
                    continue
                rows.append(values)
            add_markdown_table(document, rows)
            continue

        image_match = re.fullmatch(r"!\[(.+?)\]\((.+?)\)", stripped)
        if image_match:
            add_screenshot(document, image_match.group(1), image_match.group(2))
            index += 1
            continue

        heading_match = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        if heading_match:
            hashes, title = heading_match.groups()
            if title == "6. Walk through the architecture" and not landscape:
                add_section(document, landscape=True)
                landscape = True
            elif title == "Optional advanced demo: FGA and VP approval" and landscape:
                add_section(document, landscape=False)
                landscape = False
            elif title in PAGE_BREAK_BEFORE:
                document.add_page_break()
            level = 1 if len(hashes) == 1 else 2 if len(hashes) == 2 else 3
            paragraph = document.add_heading(level=level)
            add_inline(paragraph, title)
            index += 1
            continue

        if stripped.startswith("> "):
            add_callout(document, stripped[2:])
            index += 1
            continue

        bullet_match = re.match(r"^-\s+(.+)$", stripped)
        if bullet_match:
            paragraph = document.add_paragraph(style="List Bullet")
            paragraph.paragraph_format.space_after = Pt(2)
            add_inline(paragraph, bullet_match.group(1))
            index += 1
            continue

        numbered_match = re.match(r"^\d+\.\s+(.+)$", stripped)
        if numbered_match:
            paragraph = document.add_paragraph(style="List Number")
            paragraph.paragraph_format.space_after = Pt(2)
            add_inline(paragraph, numbered_match.group(1))
            index += 1
            continue

        paragraph = document.add_paragraph()
        if stripped.startswith("**Say:**") or stripped.startswith("**Expected:**") or stripped.startswith("**Call out:**") or stripped.startswith("**Important:**") or stripped.startswith("**Why Mike"):
            paragraph.paragraph_format.left_indent = Inches(0.15)
            paragraph.paragraph_format.right_indent = Inches(0.15)
        add_inline(paragraph, stripped)
        index += 1


def build() -> None:
    document = Document()
    document.core_properties.title = "CourtEdge ProGear Team Demo Guide"
    document.core_properties.subject = "Step-by-step customer demo guide"
    document.core_properties.author = "Johnathan Campos"
    document.core_properties.keywords = "Okta, AI Agent Governance, ID-JAG, FGA, OIG, ProGear"
    configure_styles(document)
    set_section_layout(document.sections[0], landscape=False)
    configure_headers(document)
    add_cover(document)
    parse_markdown(document, SOURCE.read_text(encoding="utf-8").splitlines())
    document.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    try:
        build()
    except Exception as exc:
        print(f"Failed to build demo guide: {exc}", file=sys.stderr)
        raise
