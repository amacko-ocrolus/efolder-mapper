# efolder-mapper — Container Mapping Tool

A Streamlit web app that uses three AI services in parallel (OpenAI, Anthropic, Gemini) to automatically map Ocrolus document form types to a lender's eFolder container names. Mappings where at least 2 of the 3 AIs agree are marked "confident"; the rest are flagged for manual review.

---

## How it works

1. Select a **preloaded Ocrolus form types file** or upload a custom one (CSV or XLSX)
2. Upload a **lender container names file** (CSV or JSON)
3. Click **Map** — all three AI services are queried in parallel
4. A results CSV is generated with two sections:
   - **Confident mappings** — 2+ AI services agreed, with average confidence score
   - **Manual review** — no consensus, showing each service's suggestion plus a recommended best guess

The app requires at least 2 of the 3 AI services to succeed before writing output. A sidebar shows live status for each service before you run.

---

## Project structure

```
efolder-mapper/
├── app.py                    # Streamlit web UI
├── mapper.py                 # CLI entrypoint (optional, no UI)
├── start.sh                  # Create venv, install deps, launch Streamlit
├── requirements.txt
├── .env.example              # Copy to .env and fill in API keys
│
├── preloaded/                # Committed Ocrolus form type CSVs (no upload needed)
│
├── services/
│   ├── ai_anthropic.py       # Anthropic Claude (claude-sonnet-4-20250514)
│   ├── ai_openai.py          # OpenAI (gpt-4o)
│   ├── ai_gemini.py          # Google Gemini (gemini-2.0-flash)
│   ├── consensus.py          # Majority-vote logic + CSV writer
│   └── ingestion.py          # CSV / XLSX / JSON file parsing
│
├── prompts/
│   └── mapping_prompt.py     # Shared prompt builder for all AI services
│
├── tests/
│   ├── test_ai_services.py
│   ├── test_consensus.py
│   └── test_ingestion.py
│
├── data/                     # Gitignored — put local working files here
└── ADMIN_SETUP.md            # One-time setup guide
```

---

## Quick start

### Prerequisites

- Python 3.10+
- API keys for OpenAI, Anthropic, and Google Gemini

### Setup

```bash
git clone https://github.com/amacko-ocrolus/efolder-mapper.git
cd efolder-mapper

cp .env.example .env
# Edit .env and paste in your three API keys

./start.sh
```

The app will be available at `http://localhost:8501`.

`start.sh` creates a virtual environment automatically — no manual `pip install` needed.

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

## API keys

Set in `.env` (never committed to git):

```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...
```

If a key is missing the service is skipped. At least 2 services must succeed per run.

---

## AI models in use

| Service | Model |
|---|---|
| OpenAI | `gpt-4o` |
| Anthropic | `claude-sonnet-4-20250514` |
| Google Gemini | `gemini-2.0-flash` |

---

## Preloaded Ocrolus files

Drop Ocrolus form type CSVs or XLSXs into the `preloaded/` directory and commit them. They'll appear in a dropdown in the UI so users don't need to re-upload the same file every run. Update when Ocrolus releases a new form type list.

```bash
cp new-ocrolus-types.csv preloaded/
git add preloaded/new-ocrolus-types.csv
git commit -m "Update Ocrolus form types"
git push origin claude/clone-containermapping-repo-L5m8Q
```

---

## Output CSV format

The output CSV has two sections:

**Section 1 — Confident mappings** (2+ services agreed):
| Form Type | Container Name | Agreed Services | Avg Confidence |
|---|---|---|---|
| W2 | Income - W-2 / 1099 | Anthropic, OpenAI | 0.95 |

**Section 2 — Manual review** (no consensus):
| Form Type | OpenAI Suggestion | Anthropic Suggestion | Gemini Suggestion | Best Guess | Best Confidence |
|---|---|---|---|---|---|
| MISC_FORM | Miscellaneous | Other Docs | Miscellaneous | Miscellaneous | 0.72 |
