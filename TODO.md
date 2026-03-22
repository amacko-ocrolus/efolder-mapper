# TODO

Current status and remaining steps for the Container Mapping Tool.

---

## Status as of 2026-03-22

The app is **built and functional**. AI services are OpenAI, Anthropic, and Ollama (local). A first end-to-end run was attempted with OpenAI and Anthropic. Two bugs were found and fixed:
- Anthropic and OpenAI services were hitting `max_tokens=4096` and returning truncated JSON → bumped to `16384`
- Google Gemini (original third service) had a free-tier quota of 0 → replaced with Ollama

---

## Next run checklist

- [ ] Ensure Ollama is running and `llama3.1` is pulled (`ollama pull llama3.1`)
- [ ] Run `./start.sh` and do a full test mapping with all three services
- [ ] Verify the output CSV looks correct — both sections (confident + review)

---

## Infrastructure (if deploying to VM)

- [ ] Provision VM (or identify existing one)
- [ ] Install Python 3.10+ and pip
- [ ] Install Ollama and pull llama3.1 (`ollama pull llama3.1`)
- [ ] Clone this repo onto the VM
- [ ] Copy `.env.example` → `.env` and paste in API keys
- [ ] Run `pip install -r requirements.txt`
- [ ] Run tests: `python -m pytest tests/ -v`
- [ ] Open port 8501 in the VM firewall
- [ ] Start the app: `./start.sh`
- [ ] Verify the app is reachable from a browser
- [ ] Share the URL with end users

---

## Nice-to-haves (later)

- [ ] Set up the app as a systemd service so it auto-restarts on reboot
- [ ] Add HTTPS via reverse proxy (nginx or caddy)
- [ ] Set up log rotation
- [ ] Consider downgrading to cheaper models (`gpt-4o-mini`, `claude-haiku`) if API costs are a concern — quality should still be sufficient for this task
