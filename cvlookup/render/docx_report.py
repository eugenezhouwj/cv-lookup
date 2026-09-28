"""Render a brief JSON into the detailed and summarised .docx reports (SPEC "Outputs")."""

from __future__ import annotations

import os
import re

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.shared import Cm, Pt, RGBColor

from .brief import (
    DEFAULT_CLASSIFICATION,
    STATUS_LABEL,
    assign_refs,
    collect_unverified,
    is_shown,
    validate,
)

FONT = "Arial"
NAVY = RGBColor(0x1F, 0x3A, 0x5F)
GREY = RGBColor(0x59, 0x59, 0x59)
LINK = RGBColor(0x1F, 0x5F, 0x9F)
STATUS_COLOUR = {"verified": RGBColor(0x2E, 0x7D, 0x32), "partial": RGBColor(0xB2, 0x6A, 0x00)}
HEADER_FILL = "DCE6F0"
KEY_FILL = "EEF3F8"
DISCLAIMER = "AI-assisted brief compiled from public sources. Verify before circulation."


# ---------------------------------------------------------------- low-level helpers


def _shade(cell, fill: str) -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def _field(paragraph, instr: str, size: Pt | None = None) -> None:
    """Insert a Word field (e.g. PAGE, NUMPAGES) that updates when opened/printed."""
    run = paragraph.add_run()
    if size:
        run.font.size = size
    for tag, attr in (("w:fldChar", "begin"), ("w:instrText", None), ("w:fldChar", "separate")):
        el = OxmlElement(tag)
        if attr:
            el.set(qn("w:fldCharType"), attr)
        else:
            el.set(qn("xml:space"), "preserve")
            el.text = instr
        run._r.append(el)
    num = paragraph.add_run("1")
    if size:
        num.font.size = size
    end = paragraph.add_run()
    el = OxmlElement("w:fldChar")
    el.set(qn("w:fldCharType"), "end")
    end._r.append(el)


def add_hyperlink(paragraph, url: str, text: str, size: Pt | None = None):
    part = paragraph.part
    r_id = part.relate_to(url, RT.HYPERLINK, is_external=True)
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), r_id)
    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    colour = OxmlElement("w:color")
    colour.set(qn("w:val"), str(LINK))
    rpr.append(colour)
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    rpr.append(underline)
    if size:
        sz = OxmlElement("w:sz")
        sz.set(qn("w:val"), str(int(size.pt * 2)))
        rpr.append(sz)
    run.append(rpr)
    t = OxmlElement("w:t")
    t.text = text
    t.set(qn("xml:space"), "preserve")
    run.append(t)
    link.append(run)
    paragraph._p.append(link)
    return link


def _bottom_border(paragraph, colour: str = "1F3A5F", size: int = 8) -> None:
    pPr = paragraph._p.get_or_add_pPr()
    borders = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    for k, v in (("w:val", "single"), ("w:sz", str(size)), ("w:space", "1"), ("w:color", colour)):
        bottom.set(qn(k), v)
    borders.append(bottom)
    pPr.append(borders)


def _force_font(styles_el) -> None:
    """Replace theme font references with Arial so every style renders in the same face."""
    for rfonts in styles_el.iter(qn("w:rFonts")):
        for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
            if rfonts.get(qn(attr)) is not None:
                del rfonts.attrib[qn(attr)]
        for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
            rfonts.set(qn(attr), FONT)


def _set_widths(table, widths_cm) -> None:
    """Fix column widths (grid + every cell) so Word, LibreOffice and Google Docs agree."""
    table.autofit = False
    grid = table._tbl.tblGrid
    for col, w in zip(grid.findall(qn("w:gridCol")), widths_cm):
        col.set(qn("w:w"), str(int(Cm(w).twips)))
    for row in table.rows:
        for cell, w in zip(row.cells, widths_cm):
            cell.width = Cm(w)


def _keep_with_next(paragraph) -> None:
    paragraph.paragraph_format.keep_with_next = True


# ---------------------------------------------------------------- document shell


def _setup(meta: dict, doc_title: str) -> Document:
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2.2)
    sec.top_margin, sec.bottom_margin = Cm(2.5), Cm(2.2)
    sec.header_distance = sec.footer_distance = Cm(1.0)

    styles = doc.styles
    _force_font(styles.element)
    normal = styles["Normal"]
    normal.font.name = FONT
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.1
    for name, size, before in (("Heading 1", 14, 16), ("Heading 2", 12, 12), ("Heading 3", 11, 10)):
        st = styles[name]
        st.font.name = FONT
        st.font.size = Pt(size)
        st.font.bold = True
        st.font.color.rgb = NAVY
        st.paragraph_format.space_before = Pt(before)
        st.paragraph_format.space_after = Pt(4)
    for name in ("List Bullet",):
        styles[name].font.name = FONT
        styles[name].font.size = Pt(11)
        styles[name].paragraph_format.space_after = Pt(3)

    classification = meta.get("classification") or DEFAULT_CLASSIFICATION

    # Header: logo (left) + classification (centre).
    header = sec.header
    hp = header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    logo = meta.get("logo_path")
    if logo and os.path.isfile(logo):
        lp = hp.insert_paragraph_before()
        lp.alignment = WD_ALIGN_PARAGRAPH.LEFT
        lp.add_run().add_picture(logo, height=Cm(1.3))
    r = hp.add_run(classification)
    r.bold = True
    r.font.size = Pt(10)

    # Footer: classification, page x of y, disclaimer.
    footer = sec.footer
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = fp.add_run(classification)
    r.bold = True
    r.font.size = Pt(10)
    pp = footer.add_paragraph()
    pp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    small = Pt(8)
    for text, instr in ((f"{doc_title}  |  Page ", "PAGE"), (" of ", "NUMPAGES")):
        run = pp.add_run(text)
        run.font.size = small
        run.font.color.rgb = GREY
        _field(pp, instr, small)
    dp = footer.add_paragraph()
    dp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = dp.add_run(DISCLAIMER)
    run.italic = True
    run.font.size = small
    run.font.color.rgb = GREY
    return doc


def _title_block(doc: Document, meta: dict, kind: str) -> None:
    p = doc.add_paragraph()
    r = p.add_run("MEETING BRIEF")
    r.bold = True
    r.font.size = Pt(10)
    r.font.color.rgb = GREY
    p.paragraph_format.space_after = Pt(0)
    p = doc.add_paragraph()
    r = p.add_run(meta["subject"])
    r.bold = True
    r.font.size = Pt(18)
    r.font.color.rgb = NAVY
    p.paragraph_format.space_after = Pt(2)
    p = doc.add_paragraph()
    r = p.add_run(kind)
    r.font.size = Pt(12)
    r.font.color.rgb = GREY
    _bottom_border(p)

    rows = [
        ("Meeting date", meta.get("meeting_date")),
        ("Purpose", meta.get("meeting_purpose")),
        ("MND attendees", meta.get("attendees")),
        ("Policy domain(s)", ", ".join(meta.get("policy_domains") or []) or None),
        ("Prepared by", meta.get("prepared_by")),
        ("Date prepared", meta.get("date_prepared")),
    ]
    rows = [(k, v) for k, v in rows if v]
    table = doc.add_table(rows=len(rows), cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    _set_widths(table, (3.6, 13.0))
    for row, (k, v) in zip(table.rows, rows):
        row.cells[0].paragraphs[0].add_run(k).bold = True
        row.cells[1].paragraphs[0].add_run(str(v))
        for c in row.cells:
            for par in c.paragraphs:
                par.paragraph_format.space_after = Pt(2)
                for run in par.runs:
                    run.font.size = Pt(10)
    doc.add_paragraph()


# ---------------------------------------------------------------- content helpers


def _sources_inline(p, sources: list[dict] | None, size=Pt(8)) -> None:
    if not sources:
        return
    r = p.add_run("  [")
    r.font.size = size
    r.font.color.rgb = GREY
    for i, s in enumerate(sources):
        if i:
            sep = p.add_run("; ")
            sep.font.size = size
            sep.font.color.rgb = GREY
        label = s.get("label") or s.get("url") or "source"
        if s.get("url"):
            add_hyperlink(p, s["url"], label, size)
        else:
            rr = p.add_run(label)
            rr.font.size = size
            rr.font.color.rgb = GREY
    r = p.add_run("]")
    r.font.size = size
    r.font.color.rgb = GREY


def _status_tag(p, status: str | None) -> None:
    if status == "partial":
        r = p.add_run(f"  ({STATUS_LABEL['partial']})")
        r.italic = True
        r.font.size = Pt(8)
        r.font.color.rgb = STATUS_COLOUR["partial"]


def _numbered(doc, n: int):
    """Numbered paragraph with explicit numbering, so lists restart for each person.

    (python-docx's 'List Number' style shares one counter across the whole document.)
    """
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.75)
    p.paragraph_format.first_line_indent = Cm(-0.75)
    p.paragraph_format.tab_stops.add_tab_stop(Cm(0.75))
    p.add_run(f"{n}.\t")
    return p


def _item_bullet(doc, text: str, item: dict, style="List Bullet", bold_prefix: str | None = None):
    p = doc.add_paragraph(style=style)
    if bold_prefix:
        p.add_run(bold_prefix).bold = True
    p.add_run(text)
    _status_tag(p, item.get("status"))
    _sources_inline(p, item.get("sources"))
    return p


def _authors_short(pub: dict) -> str:
    authors = pub.get("authors") or []
    if isinstance(authors, str):
        return authors
    if len(authors) > 3:
        return f"{authors[0]} et al."
    return ", ".join(authors)


def _pub_url(pub: dict) -> str | None:
    if pub.get("doi"):
        return f"https://doi.org/{pub['doi']}"
    return pub.get("url")


def _citation_line(p, pub: dict, ref: str | None = None, size=Pt(10)) -> None:
    if ref:
        r = p.add_run(f"[{ref}] ")
        r.bold = True
        r.font.size = size
    parts = [f"{_authors_short(pub)} ({pub.get('year') or 'n.d.'}). "]
    r = p.add_run(parts[0])
    r.font.size = size
    r = p.add_run(pub.get("title") or "Untitled")
    r.italic = True
    r.font.size = size
    tail = []
    if pub.get("type") == "working_paper":
        tail.append("Working paper")
    if pub.get("venue"):
        tail.append(pub["venue"])
    if tail:
        r = p.add_run(". " + ", ".join(tail) + ". ")
        r.font.size = size
    else:
        p.add_run(". ").font.size = size
    url = _pub_url(pub)
    if url:
        add_hyperlink(p, url, f"doi:{pub['doi']}" if pub.get("doi") else url, size)
    if pub.get("published_version"):
        r = p.add_run(f"  Published version: {pub['published_version']}")
        r.font.size = size
        r.font.color.rgb = GREY


def _citations_text(pub: dict) -> str:
    cites = pub.get("citations") or []
    if not cites:
        return "—"
    parts = [f"{c.get('source')}: {c.get('count')}" for c in cites]
    dates = sorted({c.get("retrieved") for c in cites if c.get("retrieved")})
    return "; ".join(parts) + (f" (retrieved {', '.join(dates)})" if dates else "")


def _table(doc, headers: list[str], rows: list[list], widths_cm: list[float], font=Pt(9)):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for cell, h, w in zip(table.rows[0].cells, headers, widths_cm):
        cell.width = Cm(w)
        _shade(cell, HEADER_FILL)
        run = cell.paragraphs[0].add_run(h)
        run.bold = True
        run.font.size = font
    for data in rows:
        cells = table.add_row().cells
        for cell, value, w in zip(cells, data, widths_cm):
            cell.width = Cm(w)
            par = cell.paragraphs[0]
            if callable(value):
                value(par)
            else:
                par.add_run("" if value is None else str(value))
            for r in par.runs:
                r.font.size = font
    _set_widths(table, widths_cm)
    for row in table.rows:
        for cell in row.cells:
            for par in cell.paragraphs:
                par.paragraph_format.space_after = Pt(1)
                par.paragraph_format.line_spacing = 1.0
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return table


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _summary_table(doc, pub: dict) -> None:
    s = pub.get("summary") or {}
    sg = pub.get("singapore")
    rows = [
        ("Research question", s.get("research_question")),
        ("Data", s.get("data")),
        ("Methodology", s.get("methodology")),
        ("Main findings", s.get("main_findings")),
        ("Sub-findings", s.get("sub_findings")),
        ("Relevance to meeting", s.get("relevance")),
    ]
    if sg:
        tier_txt = f"Tier {sg.get('tier')}"
        if sg.get("tier") == 1:
            body = [f"{tier_txt} — {sg.get('criterion') or 'Singapore-specific'}"]
        else:
            body = [
                f"{tier_txt} — comparable context: {sg.get('context') or 'not stated'}",
                f"Why comparable: {sg.get('comparability') or 'not stated'}",
                f"Key differences: {sg.get('differences') or 'not stated'}",
            ]
        rows.append(("Singapore relevance", body))
    basis = {"full_text": "Full text", "abstract": "Abstract only"}.get(s.get("basis"), "Not stated")
    rows.append(("Basis / verification", f"{basis}; {STATUS_LABEL.get(pub.get('status'), 'Unknown')}; citations — {_citations_text(pub)}"))

    table = doc.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    for label, value in rows:
        cells = table.add_row().cells
        cells[0].width, cells[1].width = Cm(3.6), Cm(13.0)
        _shade(cells[0], KEY_FILL)
        r = cells[0].paragraphs[0].add_run(label)
        r.bold = True
        r.font.size = Pt(9)
        items = _as_list(value) or ["not stated"]
        first = cells[1].paragraphs[0]
        for i, text in enumerate(items):
            par = first if i == 0 else cells[1].add_paragraph()
            prefix = "• " if len(items) > 1 else ""
            par.add_run(prefix + text).font.size = Pt(9)
            par.paragraph_format.space_after = Pt(1)
            par.paragraph_format.line_spacing = 1.0
        cells[0].paragraphs[0].paragraph_format.space_after = Pt(1)
    _set_widths(table, (3.6, 13.0))
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def _pub_section(doc, person: dict, key: str, refs: dict, summarised: set, heading_no: str, heading: str, intro: str | None):
    pubs = person.get("publications") or {}
    ids = [pid for pid in person.get(key) or [] if is_shown(pubs.get(pid, {}))]
    doc.add_heading(f"{heading_no} {heading}", level=2)
    if intro:
        doc.add_paragraph(intro).runs[0].font.color.rgb = GREY
    if not ids:
        doc.add_paragraph("No verified publications identified for this section.")
        return
    rows = []
    for pid in ids:
        pub = pubs[pid]
        extra = []
        if key == "singapore_relevant" and pub.get("singapore"):
            extra = [f"Tier {pub['singapore'].get('tier')}"]
        rows.append(
            [
                refs[pid],
                pub.get("title"),
                pub.get("year"),
                ("Working paper" if pub.get("type") == "working_paper" else pub.get("venue") or ""),
                _citations_text(pub) if key == "top_cited" else (extra[0] if extra else ""),
            ]
        )
    last = "Citations (by source)" if key == "top_cited" else ("Tier" if key == "singapore_relevant" else "")
    if last:
        _table(doc, ["Ref", "Title", "Year", "Venue", last], rows, [1.2, 7.4, 1.3, 3.5, 3.2])
    else:
        _table(doc, ["Ref", "Title", "Year", "Venue"], [r[:4] for r in rows], [1.2, 9.0, 1.4, 5.0])

    earlier = [refs[pid] for pid in ids if pid in summarised]
    if earlier:
        n = doc.add_paragraph()
        r = n.add_run(f"Summaries for {', '.join(earlier)} appear above.")
        r.italic = True
        r.font.size = Pt(9)
        r.font.color.rgb = GREY
    for pid in ids:
        if pid in summarised:
            continue
        summarised.add(pid)
        p = doc.add_paragraph()
        _keep_with_next(p)
        _citation_line(p, pubs[pid], refs[pid])
        _summary_table(doc, pubs[pid])


# ---------------------------------------------------------------- detailed report


def render_detailed(brief: dict, path: str) -> str:
    meta = brief["meta"]
    doc = _setup(meta, "Detailed report")
    _title_block(doc, meta, "Detailed report")
    persons = brief["persons"]

    doc.add_heading("1. Executive summary", level=1)
    for line in brief.get("executive_summary") or []:
        doc.add_paragraph(line, style="List Bullet")

    sec = 1
    for person in persons:
        sec += 1
        refs = assign_refs(person)
        summarised: set = set()
        doc.add_heading(f"{sec}. {person['name']}", level=1)
        sub = doc.add_paragraph()
        r = sub.add_run(" · ".join(x for x in (person.get("title"), person.get("affiliation")) if x))
        r.font.color.rgb = GREY

        doc.add_heading(f"{sec}.1 Background", level=2)
        for item in filter(is_shown, person.get("background") or []):
            _item_bullet(doc, item["text"], item)

        doc.add_heading(f"{sec}.2 Research interests", level=2)
        for item in filter(is_shown, person.get("research_interests") or []):
            extra = []
            if item.get("jel"):
                extra.append("JEL " + ", ".join(item["jel"]))
            ev = [refs[r] for r in item.get("refs") or [] if r in refs]
            if ev:
                extra.append("evidence " + ", ".join(ev))
            text = (item.get("description") or "") + (f" ({'; '.join(extra)})" if extra else "")
            _item_bullet(doc, text, item, bold_prefix=f"{item['theme']}: ")

        years = meta.get("recent_window_years", 3)
        n_top = meta.get("top_cited_n", 5)
        _pub_section(doc, person, "recent", refs, summarised, f"{sec}.3", "Recent publications",
                     f"Publications in the last {years} years, including working papers.")
        _pub_section(doc, person, "top_cited", refs, summarised, f"{sec}.4", "Most-cited publications",
                     f"Top {n_top} by citations. Counts differ between databases; each source is shown.")

        doc.add_heading(f"{sec}.5 Academic network", level=2)
        net = [n for n in person.get("network") or [] if is_shown(n)]
        if net:
            rows = []
            for n in net:
                def cell(par, n=n):
                    par.add_run(n.get("detail") or "")
                    _sources_inline(par, n.get("sources"))
                rows.append([
                    n.get("name"),
                    n.get("relationship"),
                    n.get("joint_works") or "",
                    "Yes" if n.get("singapore_link") else "",
                    cell,
                ])
            _table(doc, ["Name", "Relationship", "Joint works", "SG link", "Details"], rows, [3.4, 3.0, 1.6, 1.4, 7.2])
        else:
            doc.add_paragraph("No verified network information.")

        _pub_section(doc, person, "singapore_relevant", refs, summarised, f"{sec}.6", "Publications relevant to Singapore",
                     "Tier 1: Singapore-specific. Tier 2: comparable contexts, with reasons and limits on transferability.")

        doc.add_heading(f"{sec}.7 Talking points", level=2)
        for n, tp in enumerate(person.get("talking_points") or [], 1):
            p = _numbered(doc, n)
            p.add_run(tp["point"])
            linked = [refs[r] for r in tp.get("refs") or [] if r in refs]
            if linked:
                rr = p.add_run(f"  [{', '.join(linked)}]")
                rr.font.size = Pt(9)
                rr.font.color.rgb = GREY
        for title, key in (("Questions to ask", "questions"), ("Potential collaboration", "collaboration"),
                           ("Sensitivities", "sensitivities")):
            if person.get(key):
                h = doc.add_paragraph()
                h.add_run(title).bold = True
                _keep_with_next(h)
                for q in person[key]:
                    doc.add_paragraph(q, style="List Bullet")

    cross = brief.get("cross_person")
    if cross and len(persons) > 1:
        sec += 1
        doc.add_heading(f"{sec}. Across the group", level=1)
        for title, key in (("Shared co-authors", "shared_coauthors"), ("Overlapping themes", "overlapping_themes"),
                           ("Suggested division of questions", "question_split")):
            if cross.get(key):
                doc.add_heading(title, level=2)
                for x in cross[key]:
                    doc.add_paragraph(x, style="List Bullet")

    # References
    sec += 1
    doc.add_heading(f"{sec}. References", level=1)
    for person in persons:
        refs = assign_refs(person)
        if len(persons) > 1:
            doc.add_heading(person["name"], level=3)
        for pid, ref in refs.items():
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.8)
            p.paragraph_format.first_line_indent = Cm(-0.8)
            _citation_line(p, person["publications"][pid], ref, Pt(9))

    _sources_note(doc, meta, heading=f"{sec + 1}. Sources consulted")
    _appendices(doc, brief)
    doc.save(path)
    return path


def _sources_note(doc, meta: dict, heading: str | None = None) -> None:
    sources = meta.get("sources_consulted") or []
    if not sources:
        return
    if heading:
        doc.add_heading(heading, level=1)
    else:
        p = doc.add_paragraph()
        r = p.add_run("Sources")
        r.bold = True
        r.font.size = Pt(9)
        _keep_with_next(p)
    for s in sources:
        p = doc.add_paragraph(style="List Bullet" if heading else None)
        status = s.get("status", "ok")
        text = f"{s.get('name')} — {'retrieved ' + s['retrieved'] if s.get('retrieved') else ''}"
        if status != "ok":
            text = f"{s.get('name')} — UNAVAILABLE"
        if s.get("note"):
            text += f" ({s['note']})"
        r = p.add_run(text)
        r.font.size = Pt(9) if heading else Pt(8)
        if not heading:
            r.font.color.rgb = GREY
            p.paragraph_format.space_after = Pt(0)


def _appendices(doc, brief: dict) -> None:
    p = doc.add_paragraph()
    p.add_run().add_break(WD_BREAK.PAGE)
    doc.add_heading("Appendix A. Unverified items", level=1)
    items = collect_unverified(brief)
    if items:
        doc.add_paragraph(
            "These items were found but could not be verified against a primary source or two independent "
            "secondary sources. They are excluded from the main body."
        )
        _table(doc, ["Person", "Section", "Item", "Reason"],
               [[i.get("person"), i.get("section"), i.get("item"), i.get("reason")] for i in items],
               [3.0, 2.6, 5.6, 5.4])
    else:
        doc.add_paragraph("None.")

    doc.add_heading("Appendix B. Identity record", level=1)
    for person in brief["persons"]:
        ident = person.get("identity") or {}
        doc.add_heading(person["name"], level=3)
        rows = [[k, v] for k, v in (ident.get("identifiers") or {}).items() if v]

        def conf(par, ident=ident):
            par.add_run("Yes" if ident.get("confirmed") else "NO — not confirmed")
            if ident.get("confirmed_by"):
                par.add_run(f" ({ident['confirmed_by']})")

        rows.append(["Confirmed by user", conf])
        if ident.get("notes"):
            rows.append(["Notes", ident["notes"]])
        _table(doc, ["Identifier", "Value"], rows, [4.5, 12.1])
        if ident.get("sources"):
            p = doc.add_paragraph("Identity sources:")
            _sources_inline(p, ident["sources"], Pt(9))


# ---------------------------------------------------------------- summarised report

MAX_INTERESTS, MAX_KEY_PAPERS, MAX_CONNECTIONS, MAX_TP, MAX_Q = 5, 3, 5, 8, 5


def _key_box(doc, lines: list[str]) -> None:
    table = doc.add_table(rows=1, cols=1)
    _set_widths(table, (16.6,))
    cell = table.rows[0].cells[0]
    _shade(cell, KEY_FILL)
    p = cell.paragraphs[0]
    r = p.add_run("BOTTOM LINE")
    r.bold = True
    r.font.size = Pt(9)
    r.font.color.rgb = NAVY
    for line in lines:
        q = cell.add_paragraph()
        q.add_run(line).font.size = Pt(10.5)
        q.paragraph_format.space_after = Pt(2)
    doc.add_paragraph().paragraph_format.space_after = Pt(0)


def _mini_heading(doc, text: str):
    p = doc.add_paragraph()
    r = p.add_run(text.upper())
    r.bold = True
    r.font.size = Pt(10)
    r.font.color.rgb = NAVY
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(2)
    _keep_with_next(p)
    return p


def _compact(p, size=Pt(10)):
    p.paragraph_format.space_after = Pt(1)
    for r in p.runs:
        r.font.size = size
    return p


def render_summary(brief: dict, path: str) -> str:
    meta = brief["meta"]
    doc = _setup(meta, "Summary for senior management")
    _title_block(doc, meta, "Summary for senior management")

    for i, person in enumerate(brief["persons"]):
        if i:
            doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        refs = assign_refs(person)
        pubs = person.get("publications") or {}
        h = doc.add_heading(person["name"], level=1)
        h.paragraph_format.space_before = Pt(0)
        sub = doc.add_paragraph()
        r = sub.add_run(" · ".join(x for x in (person.get("title"), person.get("affiliation")) if x))
        r.font.color.rgb = GREY
        _key_box(doc, person.get("key_message") or [])

        _mini_heading(doc, "Profile")
        doc.add_paragraph(person.get("profile_short") or "").paragraph_format.space_after = Pt(2)

        interests = [x for x in person.get("research_interests") or [] if is_shown(x)][:MAX_INTERESTS]
        if interests:
            _mini_heading(doc, "Research interests")
            for x in interests:
                _compact(doc.add_paragraph(x["theme"], style="List Bullet"))

        key_ids = [pid for pid in person.get("key_papers") or [] if is_shown(pubs.get(pid, {}))][:MAX_KEY_PAPERS]
        if key_ids:
            _mini_heading(doc, "Key papers")
            rows = []
            for pid in key_ids:
                pub = pubs[pid]
                sg = pub.get("singapore") or {}
                sg_txt = sg.get("one_line") or (f"Tier {sg['tier']}" if sg.get("tier") else "—")
                finding = pub.get("one_line_finding") or (_as_list((pub.get("summary") or {}).get("main_findings")) or ["—"])[0]

                def paper_cell(par, pub=pub, ref=refs[pid]):
                    par.add_run(f"[{ref}] ").bold = True
                    par.add_run(f"{pub.get('title')} ({pub.get('year') or 'n.d.'})")

                rows.append([paper_cell, finding, sg_txt])
            _table(doc, ["Paper", "Key finding", "Singapore relevance"], rows, [5.2, 6.8, 4.6], Pt(9))

        net = [n for n in person.get("network") or [] if is_shown(n)][:MAX_CONNECTIONS]
        if net:
            _mini_heading(doc, "Key connections")
            for n in net:
                label = f"{n['name']} — {n.get('relationship') or ''}"
                if n.get("singapore_link"):
                    label += " (Singapore link)"
                _compact(doc.add_paragraph(label, style="List Bullet"))

        _mini_heading(doc, "Talking points")
        for n, tp in enumerate((person.get("talking_points") or [])[:MAX_TP], 1):
            p = _numbered(doc, n)
            p.add_run(tp["point"])
            linked = [refs[r] for r in tp.get("refs") or [] if r in refs]
            if linked:
                rr = p.add_run(f" [{', '.join(linked)}]")
                rr.font.color.rgb = GREY
            _compact(p)
        if person.get("questions"):
            _mini_heading(doc, "Questions to ask")
            for q in person["questions"][:MAX_Q]:
                _compact(doc.add_paragraph(q, style="List Bullet"))

    doc.add_paragraph()
    _sources_note(doc, meta)
    note = doc.add_paragraph()
    r = note.add_run("Full evidence, publication summaries and references are in the accompanying detailed report.")
    r.italic = True
    r.font.size = Pt(8)
    r.font.color.rgb = GREY
    doc.save(path)
    return path


# ---------------------------------------------------------------- entry point


def slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")[:60] or "brief"


def render(brief: dict, out_dir: str) -> dict:
    warnings = validate(brief)
    os.makedirs(out_dir, exist_ok=True)
    meta = brief["meta"]
    stem = f"{slug(meta['subject'])}_{meta['date_prepared']}"
    detailed = render_detailed(brief, os.path.join(out_dir, f"{stem}_detailed.docx"))
    summary = render_summary(brief, os.path.join(out_dir, f"{stem}_summary.docx"))
    return {"detailed": detailed, "summary": summary, "warnings": warnings}
