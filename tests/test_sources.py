from cvlookup.singapore import screen
from cvlookup.sources import crossref, openalex, repec, scholar


def test_reconstruct_abstract():
    assert openalex.reconstruct_abstract({"world": [1], "hello": [0]}) == "hello world"
    assert openalex.reconstruct_abstract(None) is None


def test_search_authors_ranks_affiliation_match(monkeypatch):
    fake = {
        "results": [
            {"id": "https://openalex.org/A1", "display_name": "Jane Doe", "works_count": 500,
             "last_known_institutions": [{"display_name": "Other Univ", "country_code": "US"}]},
            {"id": "https://openalex.org/A2", "display_name": "Jane Doe", "works_count": 40,
             "orcid": "https://orcid.org/0000-0001-2345-6789",
             "last_known_institutions": [{"display_name": "National University of Singapore", "country_code": "SG"}]},
        ]
    }
    monkeypatch.setattr(openalex, "get", lambda *a, **k: fake)
    out = openalex.search_authors("Jane Doe", "National University of Singapore")
    assert [c["openalex_id"] for c in out["candidates"]] == ["A2", "A1"]
    assert out["candidates"][0]["orcid"] == "0000-0001-2345-6789"


def test_coauthors_counts(monkeypatch):
    def work(i, coauthors):
        return {
            "id": f"https://openalex.org/W{i}", "publication_year": 2020 + i,
            "authorships": [{"author": {"id": "https://openalex.org/A0", "display_name": "Me"}, "institutions": []}]
            + [{"author": {"id": f"https://openalex.org/{c}", "display_name": c},
                "institutions": [{"display_name": "NUS", "country_code": "SG"}] if c == "B" else []} for c in coauthors],
        }

    monkeypatch.setattr(openalex, "_works", lambda *a, **k: [work(1, ["B", "C"]), work(2, ["B"]), work(3, ["B", "D"])])
    out = openalex.coauthors("A0")
    top = out["coauthors"][0]
    assert top["name"] == "B" and top["joint_works"] == 3 and top["singapore_affiliated"]
    assert top["first_year"] == 2021 and top["last_year"] == 2023


def test_crossref_work(monkeypatch):
    msg = {"message": {"DOI": "10.1/x", "title": ["T"], "author": [{"given": "A", "family": "B", "ORCID": "http://orcid.org/0000-0000-0000-0001"}],
                       "container-title": ["J"], "issued": {"date-parts": [[2021, 5]]}, "is-referenced-by-count": 7,
                       "abstract": "<jats:p>Some <jats:italic>text</jats:italic></jats:p>"}}
    monkeypatch.setattr(crossref, "get", lambda *a, **k: msg)
    out = crossref.work("https://doi.org/10.1/x")
    assert out["year"] == 2021 and out["authors"][0]["name"] == "A B"
    assert out["authors"][0]["orcid"] == "0000-0000-0000-0001"
    assert out["abstract"] == "Some text"


def test_repec_parse():
    html = """<html><title>Jane Doe | IDEAS/RePEc</title><div id="affiliation">Dept of Economics, NUS</div>
    <ol><li class="list-group-item">Doe, Jane, 2022. "<a href="/p/nbr/nberwo/1.html">Housing Paper</a>," NBER WP 1.
      <ol><li>Doe, Jane, 2023. "<a href="/a/eee/juecon/v1.html">Housing Paper</a>," J Urban Econ.</li></ol></li></ol></html>"""
    out = repec.parse_author_page(html, "https://ideas.repec.org/e/pdo1.html")
    assert out["affiliation"] == "Dept of Economics, NUS"
    kinds = {i["kind"]: i for i in out["items"]}
    assert kinds["working_paper"]["year"] == 2022
    assert kinds["article"]["is_other_version"] is True


def test_scholar_parse_and_captcha():
    html = """<div id="gsc_prf_in">Jane Doe</div><div class="gsc_prf_il">NUS</div>
    <table id="gsc_rsb_st"><tr><td class="gsc_rsb_std">1000</td><td class="gsc_rsb_std">500</td><td class="gsc_rsb_std">15</td></tr></table>
    <table><tr class="gsc_a_tr"><td><a class="gsc_a_at">Paper A</a><div class="gs_gray">J Doe, X Y</div><div class="gs_gray">Journal, 2020</div></td>
    <td><a class="gsc_a_ac">123</a></td><td><span class="gsc_a_h">2020</span></td></tr></table>"""
    out = scholar.parse_profile(html, "u")
    assert out["citations_total"] == "1000" and out["h_index"] == "15"
    assert out["publications"][0] == {"title": "Paper A", "authors": "J Doe, X Y", "venue": "Journal, 2020",
                                      "citations_scholar": 123, "year": 2020}
    try:
        scholar.parse_profile("<html>captcha</html>", "u")
    except scholar.SourceUnavailable:
        pass
    else:
        raise AssertionError("expected SourceUnavailable")
    assert "user=abc" in scholar.profile_url("https://scholar.google.com/citations?user=abc&hl=en")


def test_singapore_screen():
    works = [
        {"openalex_id": "W1", "title": "HDB resale prices", "abstract": None, "authors": [], "funders": []},
        {"openalex_id": "W2", "title": "Rents", "abstract": "", "funders": [],
         "authors": [{"name": "X", "institutions": [{"country": "SG"}]}]},
        {"openalex_id": "W3", "title": "Public housing in Hong Kong", "abstract": "", "authors": [], "funders": []},
        {"openalex_id": "W4", "title": "The cpf-like pension in Chile", "abstract": "", "authors": [], "funders": []},
    ]
    out = screen(works, ["housing"])
    assert [w["openalex_id"] for w in out["tier1_candidates"]] == ["W1", "W2"]
    assert [w["openalex_id"] for w in out["tier2_candidates"]] == ["W3"]
    assert screen(works, ["astrology"])["unrecognised_domains"] == ["astrology"]
