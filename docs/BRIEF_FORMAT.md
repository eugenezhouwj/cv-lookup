# Brief JSON format

`python -m cvlookup render brief.json` turns one JSON file into both reports. See
`examples/sample_brief.json` for a complete example (fictional data).

## Common conventions

- **`status`** — every background item, research interest, network entry and publication has one of
  `verified` · `partial` · `unverified`. `unverified` items are removed from the main body and listed
  in Appendix A with their `reason`.
- **`sources`** — list of `{"label", "url", "primary": bool}`. `primary: true` for DOI/Crossref records,
  institutional pages, ORCID and the person's own CV.
- Dates are ISO `YYYY-MM-DD`.

## `meta`

| Field | Required | Notes |
|---|---|---|
| `subject` | ✓ | Title line, e.g. "Prof Jane Doe (NUS) — meeting on housing supply" |
| `meeting_purpose` | ✓ | |
| `date_prepared` | ✓ | Also used in the output filenames |
| `meeting_date`, `attendees`, `policy_domains`, `prepared_by` | | Shown in the title block |
| `classification` | | Default `OFFICIAL (OPEN)` — header and footer of every page |
| `logo_path` | | PNG/JPG placed top-left in the header; omitted if missing |
| `recent_window_years`, `top_cited_n` | | Defaults 3 and 5 (used in section intros) |
| `sources_consulted` | | `[{"name","status":"ok"\|"unavailable","retrieved","note"}]` |

## Top level

- `executive_summary`: list of strings (detailed report).
- `persons`: list of person objects (below).
- `cross_person`: `{"shared_coauthors": [], "overlapping_themes": [], "question_split": []}` or `null`.
- `unverified`: extra Appendix A rows `{"person","section","item","reason"}` (items not stored elsewhere).

## Person

| Field | Notes |
|---|---|
| `name`, `title`, `affiliation` | |
| `identity` | `{"confirmed": bool, "confirmed_by", "identifiers": {label: value}, "notes", "sources"}` → Appendix B |
| `key_message` | Exactly 3 lines — who / why they matter for this meeting / recommended angle |
| `profile_short` | 2–3 sentences for the summary report |
| `background` | `[{"text", "status", "sources", "reason"?}]` |
| `research_interests` | `[{"theme", "description", "jel": [], "refs": [pub ids], "status", "sources"}]` |
| `publications` | Object keyed by your own ids (`"p1"`, …) — see below |
| `recent`, `top_cited`, `singapore_relevant` | Lists of publication ids, in display order |
| `key_papers` | 3 publication ids for the summary report |
| `network` | `[{"name", "relationship", "joint_works", "singapore_link", "detail", "status", "sources"}]` |
| `talking_points` | `[{"point", "refs": [pub ids]}]` — 5–8 |
| `questions`, `collaboration`, `sensitivities` | Lists of strings |

## Publication

```json
{
  "title": "...", "authors": ["..."], "year": 2024, "venue": "...",
  "type": "article | working_paper | book | chapter",
  "doi": "10.xxxx/yyy", "url": "used when no DOI",
  "published_version": "for working papers: citation/DOI of the journal version",
  "citations": [{"source": "OpenAlex", "count": 42, "retrieved": "2026-09-28"}],
  "status": "verified", "sources": [...], "reason": "if partial/unverified",
  "one_line_finding": "for the summary report",
  "summary": {
    "research_question": "...", "data": "...", "methodology": "...",
    "main_findings": ["..."], "sub_findings": ["..."] ,
    "relevance": "...", "basis": "full_text | abstract"
  },
  "singapore": {
    "tier": 1, "criterion": "Tier 1: which criterion is met",
    "context": "Tier 2: comparator", "comparability": "Tier 2: why similar",
    "differences": "Tier 2: limits to transferability", "one_line": "for the summary table"
  }
}
```

Publications are numbered `P1, P2, …` in order of first appearance (recent → top cited →
Singapore → key papers). Each summary is printed once, the first time the paper appears.
