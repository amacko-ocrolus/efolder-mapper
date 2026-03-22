# Server Setup (Administrators Only)

One-time setup for the VM that hosts the Container Mapping Tool. See `TODO.md` for outstanding tasks.

## 1. Get API keys

You need keys from two providers. Both offer pay-as-you-go pricing.

### OpenAI
1. Go to https://platform.openai.com and sign in (or create an account)
2. Click your profile icon → **API Keys**
3. Click **Create new secret key**, name it (e.g. "Container Mapper")
4. Copy the key (starts with `sk-`)
5. Add a payment method under **Billing** if you haven't already

### Anthropic
1. Go to https://console.anthropic.com and sign in (or create an account)
2. Go to **API Keys** in the sidebar
3. Click **Create Key**, name it (e.g. "Container Mapper")
4. Copy the key (starts with `sk-ant-`)
5. Add a payment method under **Billing** if needed

## 2. Install Ollama

Ollama is the third AI service and runs locally — no API key needed.

1. Download and install Ollama from https://ollama.com
2. Pull the model (one time, ~4.7 GB download):
   ```bash
   ollama pull llama3.1
   ```
3. Ollama runs as a background service automatically after install. Verify it's up:
   ```bash
   curl http://localhost:11434
   ```

## 3. Configure `.env`

Copy `.env.example` to `.env` and paste in your keys:

```bash
cp .env.example .env
```

```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

## 4. Start the app

```bash
./start.sh
```

This will install dependencies (if needed) and start the web app on port 8501.

## Running tests

```bash
pip install pytest
python -m pytest tests/ -v
```

## CLI (optional)

For scripting or local use without the web UI:

```bash
python mapper.py --ocrolus <ocrolus.csv> --lender <lender-file> [--output <output.csv>]
```
