# TODO

Remaining steps to get the Container Mapping Tool live.

## API Keys
- [ ] Create OpenAI API key and add billing (see ADMIN_SETUP.md §1)
- [ ] Create Anthropic API key and add billing (see ADMIN_SETUP.md §1)
- [ ] Create Google Gemini API key (see ADMIN_SETUP.md §1)

## VM Setup
- [ ] Provision VM (or identify existing one)
- [ ] Install Python 3.10+ and pip
- [ ] Clone this repo onto the VM
- [ ] Copy `.env.example` → `.env` and paste in API keys
- [ ] Run `pip install -r requirements.txt`
- [ ] Test with `python -m pytest tests/ -v`

## Networking / Access
- [ ] Open port 8501 in the VM firewall for Streamlit
- [ ] Start the app with `./start.sh`
- [ ] Verify the app is reachable from a browser
- [ ] Share the URL with end users

## Nice-to-Haves (later)
- [ ] Set up the app as a systemd service so it auto-restarts
- [ ] Add HTTPS via reverse proxy (nginx/caddy)
- [ ] Set up log rotation
