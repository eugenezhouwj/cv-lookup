---
name: cv-lookup
description: Prepare verified meeting briefs (detailed + senior-management summary, both .docx) on academic researchers, mainly economists, for MND Singapore. Use when the user asks to research, profile, look up or prepare a brief/talking points on a professor, academic or researcher ahead of a meeting, or invokes /cv-lookup.
---

# cv-lookup: research meeting brief

Follow `docs/SPEC.md`; it is the source of truth. This file says **how** to run it with
the helpers in this repo. Work from the repo root.

## 0. Setup and inputs

1. Make sure dependencies are installed: `pip install -q -r requirements.txt` (the SessionStart hook
   does this in cloud sessions).
2. Collect the inputs. **Ask the user for anything required that is missing** before starting:
   - Required: person name(s) + current affiliation; meeting purpose/objectives; policy domain(s).
   - Useful: meeting date; MND attendees/division; ORCID; Google Scholar URL; RePEc short-ID; homepage.
   - Defaults unless overridden: recent window 3 years; top-cited 5; classification `OFFICIAL (OPEN)`;
     logo = `assets/logo.png` if it exists, else none (never download or recreate a logo).
3. Create a working folder `output/<person-slug>/` for raw JSON, and keep a running list of every
   source you query with its status (`ok` / `unavailable` + reason) for `meta.sources_consulted`.

All helpers print JSON: `python -m cvlookup <command> ...`. Exit code 3 = source unavailable. Record
it and continue with the other sources. **Never fill a gap with facts you did not retrieve.**

| Purpose | Command |
|---|---|
| Candidate identities (OpenAlex + ORCID + Semantic Scholar) | `find-author "Name" --affiliation "Univ"` |
| OpenAlex profile | `author A123` |
| Recent works (incl. working papers) | `recent A123 --years 3` |
| Most cited | `top-cited A123 -n 5` |
| Co-author network | `coauthors A123 --top 15` |
| Singapore candidates (Tier 1/Tier 2) | `sg-screen A123 --domain housing [--domain trade]` |
| Publisher record for a DOI (primary source) | `doi 10.xxxx/yyy` |
| Find a DOI from a title | `crossref-search "Title" --author "Surname"` |
| ORCID record (employment, education, awards) | `orcid 0000-0000-0000-0000` |
| Semantic Scholar count/abstract/TLDR/OA PDF | `s2-paper 10.xxxx/yyy` |
| RePEc/IDEAS author page | `repec pab123` |
| Google Scholar (only if the user supplied a URL) | `scholar "<profile url>"` |
| Validate / render the brief | `validate brief.json` · `render brief.json --out output/<slug>` |

Also use WebSearch/WebFetch for institutional pages, CVs, NBER/SSRN/CEPR pages and full-text PDFs
(from `oa_url` / `oa_pdf`). If WebSearch finds a RePEc short-ID or Scholar profile, show it to the
user before relying on it.

## 1. Identity (human checkpoint)

Run `find-author`, then corroborate with ORCID, the institutional page, and RePEc if available.
**Stop and ask the user** (show one card per candidate: name, affiliation, identifiers, 3
representative papers) if any of these is true:
- more than one plausible candidate;
- identifiers disagree (e.g. ORCID on OpenAlex profile ≠ ORCID on homepage);
- the stated affiliation does not match current sources;
- the OpenAlex/S2 profile looks split (same person, several IDs) or merged (papers in unrelated fields);
- anything short of high confidence.

If the identity is unambiguous and backed by two sources, state the evidence in one line and
continue. Set `identity.confirmed: true` only once the user has confirmed, or the evidence meets
that bar; record who confirmed it and how in `identity.confirmed_by`. For split profiles,
merge the works from every confirmed OpenAlex ID yourself.

## 2. Research (SPEC step 2)

- **Background:** ORCID `employments/educations/distinctions/services/invited_positions`,
  institutional page and CV. PhD adviser only if publicly stated (e.g., CV, dissertation record).
- **Research interests:** 3–6 themes from recurring topics, JEL codes (RePEc/journal pages), and the
  person's own description. List the evidence papers (`refs`).
- **Recent:** `recent`, plus RePEc/NBER/SSRN for working papers OpenAlex misses. De-duplicate each
  working paper against its published version: one entry, with the other version in `published_version`.
  If there are more than 10, keep the 10 most relevant to the meeting purpose.
- **Top cited:** `top-cited`, then add Semantic Scholar (`s2-paper`) and Scholar counts. Keep every
  count with its source and retrieval date. Check that the top-N ordering holds across sources, and
  note any disagreement.
- **Network:** `coauthors` ranks co-authors by joint works. Add the adviser and PhD students (if
  public), NBER/CEPR/centre memberships and editorial roles. Mark `singapore_link` for NUS, NTU,
  SMU, SUTD, SUSS, MAS, A*STAR, government agencies or MND.
- **Singapore relevance:** `sg-screen` only *nominates* papers. Read each one and confirm:
  - Tier 1 → state the criterion met (Singapore data / policy / comparison / SG co-author / SG funding).
  - Tier 2 (if Tier 1 is empty, or where it adds value) → use the SPEC comparator table for the
    meeting's policy domain. Write `comparability` (why it is similar) and `differences` (what limits
    transfer to Singapore: e.g. rental vs owner-occupied leasehold, CPF financing, land ownership,
    scale, openness, institutions). You may propose other comparators if you say why.
  - Abstracts are often missing, so also check titles and full text of likely papers.

## 3. Verify (SPEC step 3)

For every item, set `status` and `sources`:
- `verified`: one primary source (`"primary": true`: DOI/Crossref record, institutional page,
  ORCID, the person's own CV) **or** two independent secondary sources (e.g. OpenAlex + RePEc).
- `partial`: one secondary source only, or sources that disagree on details. Say what's missing in `reason`.
- `unverified`: anything else. It goes to Appendix A automatically. Give a `reason`.
Check every publication's title, authors, year and venue against `doi` (Crossref) where a DOI
exists. Never cite something you have not retrieved in this run.

## 4. Summarise papers (SPEC step 4)

For each verified paper in `recent`, `top_cited` or `singapore_relevant`, read the full text
if an open-access copy exists (`oa_url` / `oa_pdf` / author page); otherwise use the abstract.
Fill in: `research_question`, `data` (source, sample, period, geography), `methodology`
(identification strategy), `main_findings` (with magnitudes where reported), `sub_findings`,
`relevance` (to the meeting and to Singapore), and `basis` (`full_text` or `abstract`). Write
`"not stated"` rather than inferring. Add a `one_line_finding` for the summary report.

## 5. Talking points and summary content (SPEC steps 5–6)

- 5–8 `talking_points`, each tied to specific papers via `refs`; 3–5 `questions`; `collaboration`
  ideas; `sensitivities` (contested findings, public positions they have taken).
- `key_message`: exactly 3 lines: who they are → why they matter for *this* meeting → recommended angle.
- `key_papers`: the 3 papers that matter most for the meeting.
- `profile_short`: 2–3 sentences.
- For more than one person: fill in `cross_person` (shared co-authors, overlapping themes, how to split questions).
- Public professional information only: nothing about family, personal life or private contact details.

## 6. Build, validate, render, deliver

1. Write `output/<slug>/brief.json` using the format in `docs/BRIEF_FORMAT.md`
   (`examples/sample_brief.json` is a complete example).
2. `python -m cvlookup validate output/<slug>/brief.json`: fix every error; fix or knowingly accept each warning.
3. `python -m cvlookup render output/<slug>/brief.json --out output/<slug>`
4. Check the result. If LibreOffice works, convert the summary to PDF and confirm it is ≤2 pages
   per person; tighten the wording if not. Skim the detailed report for gaps.
5. Give both .docx files to the user (use SendUserFile when it is available, e.g. on mobile/cloud sessions).
   Then report in chat: the identity evidence, anything partial or unverified, sources that were
   unavailable, and points they should check before circulating. `output/` is git-ignored; do not
   commit briefs.
