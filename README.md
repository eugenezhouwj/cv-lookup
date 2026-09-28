# cv-lookup

This tool prepares verified meeting briefs on academic researchers, mainly economists, for MND Singapore.
Each run produces two Word files:

- **Detailed report**: background, research interests, recent and most-cited publications, academic network,
  Singapore-relevant publications, talking points, full publication summaries, references, and appendices
  listing unverified items and the identity record.
- **Summary for senior management**: at most 2 pages per person, with the bottom line first.

The workflow is defined in [`docs/SPEC.md`](docs/SPEC.md).

## How it works

It runs inside **Claude Code** as the `/cv-lookup` skill, so no separate Anthropic API key is needed.
Claude does the reasoning: checking identity, verifying facts, summarising papers and writing talking points.
Small Python helpers in `cvlookup/` fetch data from free scholarly sources and build the .docx files.

| Source | Used for |
|---|---|
| Crossref | Publisher record for each DOI (primary source for verification) |
| ORCID | Positions, education, awards |
| OpenAlex | Author search, works, citation counts, co-author network |
| Semantic Scholar | Second citation count, abstracts, open-access PDFs |
| RePEc/IDEAS, NBER, SSRN | Economics working papers |
| Google Scholar | Only if you supply a profile URL; used to cross-check, never as the only source |

## Using it

**Laptop:** install [Claude Code](https://code.claude.com), clone this repo, then:

```bash
pip install -r requirements.txt
claude
> /cv-lookup Prof Jane Doe, National University of Singapore. Meeting 15 Oct on housing supply;
  purpose: explore collaboration on resale-market research. Domain: housing.
```

**Mobile:** open a Claude Code session on this repo in the Claude app and type the same `/cv-lookup ...` request.
A setup hook installs the dependencies automatically. The cloud environment's network access must allow
the sources above. In the environment settings, choose a broader access level or add
`api.openalex.org, api.crossref.org, pub.orcid.org, api.semanticscholar.org, ideas.repec.org, www.nber.org,
papers.ssrn.com, doi.org, scholar.google.com`, plus university sites for CVs.

Claude will stop and ask you to confirm the person's identity if there is any doubt about who they are.
The finished reports go to `output/<person>/`, which is git-ignored.

**Optional:**
- Add an official logo at `assets/logo.png` to show it in the header.
- Set `CVLOOKUP_MAILTO=you@agency.gov.sg` to use OpenAlex's and Crossref's faster "polite pool".
- Set `S2_API_KEY` if you have a Semantic Scholar API key.

## Running the helpers directly

```bash
python -m cvlookup find-author "Jane Doe" --affiliation "National University of Singapore"
python -m cvlookup recent A1234567890 --years 3
python -m cvlookup sg-screen A1234567890 --domain housing
python -m cvlookup render examples/sample_brief.json --out output/sample   # fictional sample
python -m pytest
```

Run `python -m cvlookup --help` to see every command. The brief JSON format is described in [`docs/BRIEF_FORMAT.md`](docs/BRIEF_FORMAT.md).

## Limits

- Uses public professional information only.
- Every brief carries the classification label (default **OFFICIAL (OPEN)**) and a notice that it is
  AI-assisted and must be checked before circulation.
- If a source can't be reached, the brief says so rather than filling the gap.
