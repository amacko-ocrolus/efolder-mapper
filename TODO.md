# TODO

Current status and remaining steps for the Container Mapping Tool.

---

## Status as of 2026-03-21

The app is **built and functional**. A first end-to-end run was attempted. Two bugs were found and fixed:
- Anthropic and OpenAI services were hitting `max_tokens=4096` and returning truncated JSON → bumped to `16384`
- Google free-tier quota is exhausted (see below)

---

## Blocking: Google API quota

The Google Gemini free tier has a quota of 0 for `gemini-2.0-flash`. Two options:
- **Option A (recommended for now):** Leave `GOOGLE_API_KEY` blank in `.env` — app works fine with OpenAI + Anthropic only
- **Option B:** Upgrade the Google AI project to a paid plan at aistudio.google.com

---

## Next run checklist

- [ ] Decide on Google API plan (Option A or B above)
- [ ] Update `.env` accordingly (blank the key, or add a paid-tier key)
- [ ] Run `./start.sh` and do a full test mapping
- [ ] Verify the output CSV looks correct — both sections (confident + review)

---

## Infrastructure (if deploying to VM)

- [ ] Provision VM (or identify existing one)
- [ ] Install Python 3.10+ and pip
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
