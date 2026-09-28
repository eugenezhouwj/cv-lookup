import copy
import json
import pathlib

import pytest
from docx import Document

from cvlookup.render.brief import BriefError, assign_refs, collect_unverified, validate
from cvlookup.render.docx_report import render

SAMPLE = json.loads((pathlib.Path(__file__).parent.parent / "examples" / "sample_brief.json").read_text())


def _text(path):
    doc = Document(path)
    parts = [p.text for p in doc.paragraphs]
    for t in doc.tables:
        for row in t.rows:
            parts.extend(c.text for c in row.cells)
    header = [p.text for p in doc.sections[0].header.paragraphs]
    footer = [p.text for p in doc.sections[0].footer.paragraphs]
    return "\n".join(parts), "\n".join(header), "\n".join(footer)


def test_sample_is_valid():
    assert validate(SAMPLE) == []


def test_render_both_reports(tmp_path):
    out = render(copy.deepcopy(SAMPLE), str(tmp_path))
    body, header, footer = _text(out["detailed"])
    assert "OFFICIAL (OPEN)" in header and "OFFICIAL (OPEN)" in footer
    assert "Verify before circulation" in footer
    for heading in ("Background", "Research interests", "Recent publications", "Most-cited publications",
                    "Academic network", "Publications relevant to Singapore", "Talking points"):
        assert heading in body
    # Unverified items are excluded from the main body and listed in Appendix A.
    appendix = body.split("Appendix A")[1]
    main = body.split("Appendix A")[0]
    assert "government housing advisory panel" not in main
    assert "government housing advisory panel" in appendix
    assert "Unlocated Conference Paper" in appendix
    assert "Unlocated Conference Paper" not in main
    # Tier 2 comparability and differences are shown.
    assert "Key differences" in body

    sbody, sheader, _ = _text(out["summary"])
    assert "BOTTOM LINE" in sbody and "KEY PAPERS" in sbody
    assert "Unlocated Conference Paper" not in sbody


def test_classification_override(tmp_path):
    brief = copy.deepcopy(SAMPLE)
    brief["meta"]["classification"] = "RESTRICTED"
    out = render(brief, str(tmp_path))
    _, header, _ = _text(out["summary"])
    assert "RESTRICTED" in header


def test_refs_skip_unverified():
    refs = assign_refs(SAMPLE["persons"][0])
    assert "p6" not in refs
    assert refs["p1"] == "P1"


def test_collect_unverified():
    items = collect_unverified(SAMPLE)
    assert {i["section"] for i in items} == {"Background", "Publication"}


def test_invalid_reference_is_error():
    brief = copy.deepcopy(SAMPLE)
    brief["persons"][0]["recent"].append("missing")
    with pytest.raises(BriefError):
        validate(brief)


def test_bad_status_is_error():
    brief = copy.deepcopy(SAMPLE)
    brief["persons"][0]["background"][0]["status"] = "probably"
    with pytest.raises(BriefError):
        validate(brief)


def test_warnings_for_spec_gaps():
    brief = copy.deepcopy(SAMPLE)
    p = brief["persons"][0]
    p["identity"]["confirmed"] = False
    del p["publications"]["p4"]["singapore"]["differences"]
    p["publications"]["p1"]["summary"]["basis"] = None
    warnings = "\n".join(validate(brief))
    assert "identity.confirmed" in warnings
    assert "Tier 2" in warnings
    assert "basis" in warnings
