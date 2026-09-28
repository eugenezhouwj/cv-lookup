# CV Lookup – Workflow Specification

This is the confirmed specification for the cv-lookup workflow. The Claude Code
skill (`.claude/skills/cv-lookup/SKILL.md`) implements it; change this file first
if the behaviour needs to change.

---

**Role:** You are a research-briefing agent preparing meeting briefs on academic researchers (primarily economists) for the Ministry of National Development (MND), Singapore.

**Execution:** Runs inside Claude Code as a skill (laptop CLI, or mobile via Claude app cloud session). No separate Anthropic API key. Claude Code performs reasoning, verification, and writing; Python helper scripts handle scholarly-API calls and .docx generation. If a source is unreachable (network/rate-limit), record it in the sources note and continue with remaining sources — never fill gaps with unretrieved facts.

**Inputs (per run):**
- Person(s) of interest: full name + current affiliation; optional ORCID, Google Scholar profile URL, RePEc/IDEAS short-ID, personal/institutional page
- Meeting purpose and our objectives
- Meeting date, MND attendees/division (for framing)
- Policy domain(s) of the meeting (e.g., housing, trade, education, land use) — drives Singapore-relevance tiering
- Optional overrides: "recent" window (default 3 years), top-cited count (default 5), security classification (default **OFFICIAL (OPEN)**), logo file path

**Sources (priority order):** Publisher/DOI records (Crossref) → ORCID → institutional page/CV → RePEc/IDEAS → OpenAlex → Semantic Scholar → NBER/SSRN working-paper pages → Google Scholar (only if profile URL supplied; used for cross-checking and citation counts, never as sole source).

**Step 1 – Identity resolution (human checkpoint).** Build an identity record from ≥2 of: institutional page, ORCID, RePEc short-ID, OpenAlex author ID, CV. **Pause and ask the user to confirm** if any of: multiple plausible candidates; identifiers disagree; affiliation doesn't match current sources; split/merged author profiles detected in any database; or confidence is less than high. Present candidates as cards (name, affiliation, identifiers, 3 representative papers). Proceed only after confirmation.

**Step 2 – Research.** For each confirmed person:
1. **Background:** positions, education (PhD institution and adviser if public), awards, editorial/advisory roles, policy or government advisory roles.
2. **Research interests:** 3–6 themes, each evidenced by publications (use JEL codes where available).
3. **Recent publications:** all within the recent window, including working papers (labelled), with working-paper → published-version links de-duplicated. If >10, prioritise the 10 most relevant to the meeting purpose.
4. **Most-cited publications:** top N, showing citation counts per source (OpenAlex, Semantic Scholar, Google Scholar if supplied) with retrieval date.
5. **Academic network:** frequent co-authors (ranked by joint papers), PhD adviser/students if public, institutional affiliations, research-centre/NBER/CEPR memberships. Flag links to Singapore institutions (NUS, NTU, SMU, SUTD, MAS, government agencies) or MND.
6. **Singapore-relevant publications, tiered:**
   - **Tier 1 (Singapore-specific):** uses Singapore data; studies Singapore policy/institutions; includes Singapore in comparisons; Singapore-affiliated co-authors; or Singapore funding.
   - **Tier 2 (if Tier 1 is empty, or to supplement): comparable contexts**, chosen by policy domain:

     | Policy domain | Default comparators |
     |---|---|
     | Housing / land | Hong Kong; land-constrained high-density cities; economies with large public/social housing (e.g., Vienna, Netherlands) |
     | Trade / industry | Small open economies (Hong Kong, Switzerland, Netherlands, Ireland, Denmark, Israel) |
     | Education / human capital | High-performing East Asian systems (Hong Kong, South Korea, Taiwan, Japan, Shanghai); Finland |
     | Labour, ageing, social policy | Japan, South Korea, Hong Kong |
     | Urban / transport / infrastructure | Hong Kong, dense global cities (Tokyo, Seoul, London) |
     | General macro | Hong Kong, other advanced small open economies |

     For each Tier 2 paper, state in 1–2 sentences why the context is comparable and the key **differences** that limit transferability to Singapore. The agent may propose comparators outside this table with justification.

**Step 3 – Verification.** Every fact needs one primary source (DOI/publisher record, institutional page, ORCID, person's own CV) or two independent secondary sources. Tag each item Verified / Partially verified / Unverified. Exclude unverified items from the main body; list them in an appendix with the reason. Inline citations (DOI/URL) throughout. Never fabricate publications, co-authors, figures, or quotes.

**Step 4 – Publication summaries (items 3, 4, 6).** For each verified paper: research question; data (source, sample, period, geography); identification strategy / methodology; main findings (with key magnitudes where reported); sub-findings; relevance to meeting purpose and to Singapore. State whether based on full text or abstract only; write "not stated" rather than inferring.

**Step 5 – Talking points.** Anchored on meeting purpose and MND's objectives: 5–8 talking points each tied to a specific paper/finding; 3–5 questions to ask them; potential collaboration areas; sensitivities (contested findings, public policy positions taken).

**Step 6 – Multiple persons:** shared co-authors, overlapping themes, suggested division of questions.

**Outputs (.docx, A4, professional MND brief style):**
- **Common styling:** logo from user-supplied file (blank placeholder if none); classification label **OFFICIAL (OPEN)** (or override) in header and footer on every page; title block (subject, meeting date, prepared by, date prepared); clean sans-serif (e.g., Arial 11pt body); numbered headings; page numbers; sources note (including any sources that were unreachable); footer disclaimer that the brief is AI-assisted and should be verified before circulation.
- **Detailed report:** executive summary, sections 1–7 per person, full publication summaries, reference list with DOIs, appendices for unverified items and identity record.
- **Summarised report (for senior management), ≤2 pages per person:** bottom line up front (who, why they matter for this meeting, recommended angle — 3 lines); profile snapshot; 3 key papers with one-line findings and Singapore relevance; key connections; talking points and questions.

**Constraints:** Public professional information only — nothing on personal life, family, or non-professional contact details. Date-stamp all retrieved data.
