# CLAUDE.md — Container Mapping Tool

> **For Claude Code sessions:** This file is the authoritative reference for this codebase.
> Read it in full before making any changes. After completing any task that adds, removes,
> or changes functionality, update the relevant sections of this file and commit the update
> in the same PR/commit. Keep it accurate and current — future sessions depend on it.

---

## What this tool does

The Container Mapping Tool maps **Ocrolus document form types** to a lender's **Encompass eFolder container names** using AI consensus. Three AI services (OpenAI, Anthropic, Gemini) are queried in parallel. Where 2+ services agree with sufficient confidence, the mapping is marked "confident." Everything else is flagged for manual review.

The output is an Excel (.xlsx) file delivered to the user as a download, formatted for immediate client delivery.

---

## Running the tool

```bash
cd ~/efolder-mapper-local   # or wherever the repo is cloned
./start.sh                  # creates venv, installs deps, launches Streamlit
```

App is available at `http://localhost:8501`. Restart after any `.env` change.

### Running tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

### CLI (no UI)

```bash
python mapper.py --ocrolus <ocrolus.csv> --lender <lender-file> [--output <output.csv>]
```

---

## Environment variables (`.env`)

```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...

# Optional — enables run history (see Run History section)
GCS_BUCKET_NAME=your-bucket-name
GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
```

Keys are short-lived and expire. If all three services return 401/400 errors, the keys need to be refreshed. Update `.env` and restart `./start.sh` — a page refresh is not enough.

---

## Project structure

```
efolder-mapper/
├── app.py                    # Streamlit web UI (primary entrypoint)
├── mapper.py                 # CLI entrypoint (no UI, same logic as app.py)
├── start.sh                  # Bootstrap script: venv + pip + streamlit
├── requirements.txt
├── .env.example              # Template — copy to .env and fill in keys
├── CLAUDE.md                 # This file — keep updated
│
├── preloaded/
│   ├── docs list mar 2026.csv   # Ocrolus form types list (preloaded in UI dropdown)
│   └── table-data.csv           # Form Type → Attachment Name lookup (2034 rows)
│
├── services/
│   ├── __init__.py
│   ├── ai_openai.py          # OpenAI GPT-4o integration
│   ├── ai_anthropic.py       # Anthropic Claude integration
│   ├── ai_gemini.py          # Google Gemini integration
│   ├── consensus.py          # Majority-vote logic + Excel output writer
│   ├── ingestion.py          # File parsing (CSV / XLSX / JSON)
│   ├── history.py            # GCS-backed run history (optional)
│   └── json_repair.py        # JSON extraction / repair utility
│
├── prompts/
│   └── mapping_prompt.py     # Shared prompt builder used by all three AI services
│
└── tests/
    ├── test_ai_services.py
    ├── test_consensus.py
    ├── test_exhaustive.py
    └── test_ingestion.py
```

---

## How a mapping run works (end to end)

1. **Ingestion** — `services/ingestion.py`
   - User selects a preloaded Ocrolus CSV or uploads their own (CSV or XLSX)
   - User uploads a lender container names file (CSV or JSON)
   - `load_ocrolus_types()` returns a sorted, deduplicated list of form type strings
   - `load_lender_containers()` returns a sorted, deduplicated list of container name strings
   - `load_attachment_names()` loads `preloaded/table-data.csv` → `{form_type: attachment_name}` dict

2. **AI mapping** — `services/ai_openai.py`, `ai_anthropic.py`, `ai_gemini.py`
   - All three services queried in parallel via `ThreadPoolExecutor`
   - Each service receives the full prompt from `prompts/mapping_prompt.py`
   - Large form type lists are batched (batch size 150 for OpenAI, varies by service)
   - Each service returns `{form_type: (container_name, confidence_float)}`
   - Minimum 2 services must succeed; if fewer succeed the run aborts

3. **Consensus** — `services/consensus.py` → `build_consensus()`
   - For each form type, counts how many services agree on the same container
   - **Confident:** 2+ services agree AND average confidence ≥ 0.85
   - **Review:** No majority agreement OR confidence below threshold
   - Returns `(confident_rows, review_rows)`

4. **Output** — `services/consensus.py` → `write_output_xlsx()`
   - Generates a formatted `.xlsx` file (see Output Format section below)
   - File is served as a download in the Streamlit UI
   - If GCS is configured, the file is also archived to cloud storage

---

## AI services

| Service   | Model                      | Batch size |
|-----------|----------------------------|------------|
| OpenAI    | `gpt-4o`                   | 150        |
| Anthropic | `claude-sonnet-4-20250514` | (full)     |
| Gemini    | auto-detected best available | (full)   |

Each service module exposes:
- `SERVICE_NAME: str` — display name used in UI and logs
- `get_mappings(ocrolus_types, lender_containers) -> dict[str, tuple[str, float]]`

---

## Consensus engine details (`services/consensus.py`)

```
CONFIDENCE_THRESHOLD = 0.85
```

- A mapping needs **2+ services to vote for the same container** AND **avg confidence ≥ 0.85** to be "confident"
- Agreements below the threshold are demoted to manual review
- NO_MATCH votes are excluded from consensus counting
- For review rows: `best_guess` = the suggestion with the highest individual confidence score

---

## Output format (CSV)

The output is a single flat CSV table — no section headers, no blank rows, first row is
column headers. All form types (confident and review) appear in one unified list.

**Columns:**
| Column | Description |
|--------|-------------|
| `Form Type` | Ocrolus form type string, verbatim |
| `Attachment Name` | From `preloaded/table-data.csv` lookup, verbatim |
| `Container Name` | AI-suggested container (agreed container for confident rows; best guess for review rows) |
| `Confidence Score` | avg_confidence for confident rows; best_confidence for review rows |

**No vendor names exposed** — AI service names (OpenAI, Anthropic, Gemini) never appear
in the output file.

**Row ordering:** Confident rows first, then review rows (both groups maintain alphabetical
order inherited from the Ocrolus input file).

---

## Attachment Name lookup

`preloaded/table-data.csv` — 2034 rows, columns: `Form Type | Container Name | Attachment Name | ...`

- Loaded once at app startup into `_attachment_names: dict[str, str]`
- Lookup is an **exact string match** on `Form Type`
- Populates the `Attachment Name` column in both output sections
- Returns empty string for unrecognised form types
- Values include dynamic Encompass templates like `{$FIELDS.field_id:label}` — these are preserved verbatim, never modified

---

## Preloaded Ocrolus files

Files in `preloaded/` ending in `.csv` or `.xlsx` (except `table-data.csv`) appear in
the UI dropdown so users don't need to upload the same file repeatedly.

To add a new preloaded file:
```bash
cp new-ocrolus-types.csv preloaded/
git add preloaded/new-ocrolus-types.csv
git commit -m "Add new Ocrolus form types file"
git push
```

`table-data.csv` is excluded from the dropdown automatically because `app.py` filters
for files not starting with `.` — but note: if this file were named differently it could
accidentally appear. Keep it named `table-data.csv`.

---

## Run history (optional GCS feature)

`services/history.py` — gracefully no-ops if `GCS_BUCKET_NAME` is not set.

When configured:
- Every successful run uploads the output XLSX to GCS: `runs/{YYYYMMDD_HHMMSS}_{lender_name}.xlsx`
- GCS blob metadata stores: `lender_filename`, `confident_count`, `review_count`, `services_used`
- A "Previous Runs" expander appears at the bottom of the Streamlit UI
- Retention: 180 days, enforced by GCS lifecycle policy (not in code)

GCS setup (one-time, done by admin):
1. Create bucket in Google Cloud Console
2. Create service account with Storage Object Admin role on that bucket
3. Download JSON key
4. Set 180-day lifecycle delete rule on bucket
5. Add `GCS_BUCKET_NAME` and `GOOGLE_APPLICATION_CREDENTIALS` to `.env`

---

## Prompt architecture (`prompts/mapping_prompt.py`)

All three AI services use the same prompt, built by `build_mapping_prompt()`.

The prompt includes `OCROLUS_NAMING_GUIDE` — a detailed explanation of Ocrolus's non-obvious
form type naming conventions (e.g. `A_` prefix = annotated IRS form, bare numbers = GSE forms,
year suffixes, schedule suffixes). This guide is critical to accurate mapping — do not remove
or shorten it without testing the impact on output quality.

Key prompt rules enforced:
- Must return raw JSON only (`{form_type: {container, confidence}}`)
- NO_MATCH is not allowed — always pick closest container
- Disclosures/Notices/Acknowledgments → disclosure containers, not subject-matter containers
- Confidence 0.0–1.0

---

## Git workflow

Branch: `claude/clone-containermapping-repo-L5m8Q`

```bash
git add <files>
git commit -m "description"
git push -u origin claude/clone-containermapping-repo-L5m8Q
```

The Mac local clone at `~/efolder-mapper-local` must `git pull` after server-side commits
to get updates. The Streamlit app must be restarted after pulling.

---

## Business rules (do not break these)

1. **Minimum 2 AI services must succeed** — the app hard-stops if fewer than 2 return results
2. **Form type strings are never transformed** — they are passed through verbatim from the
   Ocrolus CSV to the lookup and to the output. Altering them would break the attachment name lookup.
3. **Attachment names are verbatim** — values from `table-data.csv` column C are written to
   output exactly as-is, including `{$FIELDS...}` templates. Never clean, truncate, or modify them.
4. **No vendor names in output** — OpenAI, Anthropic, Gemini must not appear in the output file.
5. **No confidence scores in output** — these are internal only.
6. **Output column D (Section 1) and last column (Section 2)** are always empty — they exist
   for the client to fill in manual corrections.
7. **CONFIDENCE_THRESHOLD = 0.85** — changing this shifts the balance between confident and
   review rows. Requires re-testing before changing.

---

## Testing

```bash
python -m pytest tests/ -v
```

- `test_consensus.py` — covers `build_consensus()` and `write_output_xlsx()`
- `test_ingestion.py` — covers all file loading functions
- `test_ai_services.py` — covers JSON parsing for each AI service
- `test_exhaustive.py` — broader integration-style tests

All tests must pass before committing. After any change to `consensus.py`, run
`test_consensus.py` at minimum.

---

## Common failure modes

| Symptom | Cause | Fix |
|---------|-------|-----|
| All services return 401/400 | API keys expired | Update `.env`, restart `./start.sh` |
| Page refresh doesn't fix key errors | `load_dotenv()` caches at startup | Full restart required |
| Attachment Name column blank for many rows | Form type format mismatch vs `table-data.csv` | Check exact string match |
| Git push rejected (403) | JWT proxy token expired (server-side) | Push from Mac clone instead |
| Git push rejected (fetch first) | Remote has commits Mac doesn't have | `git pull --rebase` then push |
