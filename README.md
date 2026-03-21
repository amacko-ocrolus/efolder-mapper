# efolder-mapper — Container Mapping Tool

A Streamlit web app that uses three AI services in parallel (OpenAI, Anthropic, Google Gemini) to automatically map Ocrolus document form types to a lender's eFolder container names. Mappings where at least 2 of the 3 AIs agree are marked "confident"; the rest are flagged for manual review.

---

## How it works

1. Upload an **Ocrolus form types CSV** (one form type per row)
2. Upload a **lender container names file** (CSV or JSON)
3. Click **Map** — all three AI services are queried in parallel
4. A results CSV is generated with two sections:
   - **Confident mappings** — 2+ AI services agreed
   - **Manual review** — no consensus, showing each service's suggestion side-by-side

The app requires at least 2 of the 3 AI services to succeed before writing output.

---

## Project structure

```
efolder-mapper/
├── app.py                    # Streamlit web UI
├── mapper.py                 # CLI entrypoint (optional, no UI)
├── start.sh                  # Install deps + launch Streamlit
├── requirements.txt
├── .env.example              # Copy to .env and fill in API keys
│
├── services/
│   ├── ai_anthropic.py       # Anthropic Claude (claude-sonnet-4-20250514, max_tokens=16384)
│   ├── ai_openai.py          # OpenAI (gpt-4o, max_tokens=16384)
│   ├── ai_google.py          # Google Gemini (gemini-2.0-flash)
│   ├── consensus.py          # Majority-vote logic + CSV writer
│   └── ingestion.py          # CSV/JSON file parsing
│
├── prompts/
│   └── mapping_prompt.py     # Shared prompt builder for all AI services
│
├── tests/
│   ├── test_ai_services.py
│   ├── test_consensus.py
│   └── test_ingestion.py
│
├── data/                     # Gitignored data directory (put input files here locally)
├── TODO.md                   # Outstanding tasks and current status
└── ADMIN_SETUP.md            # One-time server/API key setup guide
```

---

## Quick start

### Prerequisites

- Python 3.10+
- API keys for at least 2 of: OpenAI, Anthropic, Google Gemini
- Billing enabled on whichever APIs you use (see `ADMIN_SETUP.md`)

### Setup

```bash
git clone <repo-url>
cd efolder-mapper

cp .env.example .env
# Edit .env and paste in your API keys

./start.sh
```

The app will be available at `http://localhost:8501`.

### Running tests

```bash
pip install pytest
python -m pytest tests/ -v
```

### CLI (no UI)

```bash
python mapper.py --ocrolus <ocrolus.csv> --lender <lender-file> [--output <output.csv>]
```

---

## API keys

Set in `.env`:

```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AI...
```

If you leave a key blank, that service is skipped. The app needs at least 2 services to succeed per run.

**Google note:** The free tier for Gemini has a daily quota limit of 0 for `gemini-2.0-flash` (as of this writing). Either upgrade to a paid Google AI plan, or leave `GOOGLE_API_KEY` blank and rely on OpenAI + Anthropic only.

---

## AI models in use

| Service | Model | Max output tokens |
|---|---|---|
| Anthropic | `claude-sonnet-4-20250514` | 16,384 |
| OpenAI | `gpt-4o` | 16,384 |
| Google | `gemini-2.0-flash` | (model default) |

`max_tokens` was increased from 4096 → 16384 for Anthropic and OpenAI after large inputs caused truncated JSON responses on first run.

---

## Output CSV format

The output CSV has two sections separated by a blank row:

**Section 1 — Confident mappings:**
| Form Type | Container Name | Agreed Services |
|---|---|---|
| W2 | W-2 Documents | Anthropic, OpenAI |

**Section 2 — Manual review:**
| Form Type | Anthropic Suggestion | OpenAI Suggestion | Google Suggestion |
|---|---|---|---|
| MISC_FORM | Miscellaneous | NO_MATCH | Other Docs |
