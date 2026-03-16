# vessel

Self-hosted email server with an AI sidecar agent that watches your inbox, classifies emails via LLM, and executes workflows (auto-reply, notify, ignore).

**Stack:** docker-mailserver (Postfix + Dovecot) · Mailgun relay · OpenRouter LLM · Python inotify agent


## Architecture

```
Internet → Postfix (port 25) → Dovecot → Maildir (./docker-data/dms/mail-data/)
                                                        ↑ read-only mount
                                               mail-agent (inotify watcher)
                                                        ↓
                                             OpenRouter LLM (classify)
                                                        ↓
                                     reply via SMTP · webhook notify · ignore
```

The agent container mounts the mail volume read-only and watches `new/` via inotify. It never touches the mailserver process directly.


## Prerequisites

- Docker + Docker Compose v2
- A domain with DNS control (`example.com` → swap for yours)
- Hetzner (or any VPS) with ports 25, 80, 143, 465, 587, 993 open
- Mailgun account (outbound relay — port 25 outbound is blocked on most VPS)
- OpenRouter API key

## Production setup

### 1. DNS records

| Type | Name | Value |
|------|------|-------|
| A | `mail.example.com` | `<your VPS IP>` |
| MX | `example.com` | `mail.example.com` (priority 10) |
| TXT | `example.com` | `v=spf1 include:mailgun.org ~all` |
| TXT | `_dmarc.example.com` | `v=DMARC1; p=none; rua=mailto:dmarc@example.com` |
| PTR | `<your VPS IP>` | `mail.example.com` (set in Hetzner panel) |

DKIM is handled by docker-mailserver — it generates the key; you add the TXT record it outputs.

### 2. Clone and configure

```bash
git clone <repo> vessel && cd vessel

# Mailserver config
cp mailserver.env.example mailserver.env   # edit as needed

# Agent config
cp agent/.env.example agent/.env
```

Edit `agent/.env`:

```bash
MAIL_DOMAIN=example.com
MAIL_USER=you
MAIL_PASSWORD=<your mailbox password>
OPENROUTER_API_KEY=sk-or-...
NOTIFY_WEBHOOK_URL=https://hooks.slack.com/...   # optional
```

Update hostname in compose.yaml for mailserver

### 3. Obtain the first TLS certificate

Port 80 must be free (certbot uses standalone mode):

```bash
CERTBOT_EMAIL=you@example.com DOMAIN=mail.example.com ./scripts/certbot-renew.sh
```

Certs land in `./docker-data/certbot/certs/`. The `certbot` compose service handles renewals automatically every 12 hours thereafter.

### 4. Create the mailbox

```bash
docker compose run --rm mailserver setup email add you@example.com <password>
docker compose run --rm mailserver setup dkim
```

Copy the DKIM public key it prints and add it to your DNS as a TXT record.

### 5. Start everything

```bash
docker compose up -d
docker compose logs -f mail-agent
```

Confirm the agent is watching:
```
2025-03-10 12:00:00 INFO Loaded 4 workflows
2025-03-10 12:00:00 INFO Watching /var/mail/example.com/test/new
```

### 6. Edit workflows

Open `agent/config.yml` to adjust intents, reply prompts, or add new workflows. The agent reads the config at startup — `docker compose restart mail-agent` to apply changes.


## Testing

> **Important:** The full test suite (unit tests + e2e) requires a **Linux environment**. The agent depends on `inotify_simple`, which is a Linux-only kernel API. On macOS, you can only run unit tests using `requirements-test.txt` (which excludes `inotify_simple`).

### Unit tests (no Docker, no live services)

On Linux:

```bash
cd agent
pip install -r requirements.txt pytest
pytest tests/ -v
```

On macOS (uses `requirements-test.txt` — excludes `inotify_simple`):

```bash
cd agent
uv run --with "$(paste -sd, requirements-test.txt)" pytest tests/ -v
```

Tests cover:
- `test_parser.py` — plain text, HTML fallback, multipart, truncation, missing headers
- `test_classifier.py` — exact match, case-insensitive, garbage LLM output, LLM exception
- `test_blocklist.py` — noreply pattern, List-Unsubscribe header, self-address, normal sender pass-through

All LLM, SMTP, and IMAP calls are mocked — no external dependencies needed.

### Dry-run the pipeline against a real email file

Drop a `.eml` file anywhere and parse/classify it without sending anything. Requires `OPENROUTER_API_KEY` — this makes a real LLM call:

```bash
export MAIL_DOMAIN=example.com MAIL_USER=you OPENROUTER_API_KEY=sk-or-...

cd agent
python - <<'EOF'
from parser import parse
import classifier, yaml

with open("config.yml") as f:
    cfg = yaml.safe_load(f)

em = parse("/path/to/some-email.eml")
result = classifier.classify(em, cfg["workflows"])
print(f"from={em.from_email!r} subject={em.subject!r} → {result}")
EOF
```

### End-to-end test (Linux / production server)

Requires Docker, TLS certs, and a running mailserver. Run on your production server or any Linux box with the full setup:

```bash
# 1. Start the mailserver and wait for it to become healthy
docker compose up -d mailserver

# 2. Create a mailbox (skip if already done)
docker compose exec mailserver setup email add you@example.com <password>

# 3. Start the agent
docker compose up -d mail-agent

# 4. Watch the agent logs
docker compose logs -f mail-agent
```

You should see:
```
INFO Loaded 4 workflows
INFO Watching /var/mail/example.com/you/new
```

**Inject a test email directly into the Maildir** (bypasses SMTP — instant trigger):

```bash
./scripts/inject-test-email.sh "Can we schedule a call?"
```

The agent should log the classification and action within ~1 second.

**Send a real email via SMTP** (tests the full delivery path):

```bash
# Requires swaks (apt install swaks)
swaks \
  --to you@example.com \
  --from alice@example.com \
  --server localhost:587 \
  --auth LOGIN \
  --auth-user you@example.com \
  --auth-password <password> \
  --tls \
  --body "Can we schedule a call this week?"
```

### Test idempotency

```bash
# Inject a test email and wait for it to be processed
./scripts/inject-test-email.sh "Idempotency test"
sleep 2

# Check the state file — should contain the injected filename
cat docker-data/agent/processed.txt

# Restart the agent — same file must NOT be processed again
docker compose restart mail-agent
sleep 3
docker compose logs mail-agent | grep -i "already processed"
```

## Workflow configuration reference

Edit `agent/config.yml`:

```yaml
workflows:
  - name: "my-workflow"
    match:
      intent: "describe what this email is about in plain English"
    action:
      type: reply | ignore | notify
      prompt: "System prompt for reply generation"   # reply only
      webhook: "${WEBHOOK_URL}"                       # notify only
```

- **`reply`** — generates a reply via LLM and sends it via SMTP. Blocklist is always checked first.
- **`ignore`** — logs and discards. Good for spam/newsletters.
- **`notify`** — POSTs a JSON summary to a webhook (Slack, Discord, n8n, etc).
- The `fallback` workflow must be last — it catches anything unmatched.

Environment variables (`${VAR}`) in `config.yml` are resolved at startup.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Agent exits immediately | `docker compose logs mail-agent` — watch path probably doesn't exist yet; create the mailbox first |
| Emails not triggering the agent | Confirm `new/` has the right path: `ls docker-data/dms/mail-data/<domain>/<user>/new/` |
| Reply not delivered | Check `docker compose logs mailserver` for SMTP relay errors; verify Mailgun credentials in `mailserver.env` |
| IMAP append failing | Confirm `MAIL_PASSWORD` matches the Dovecot mailbox password |
| LLM always returns `fallback` | Check `OPENROUTER_API_KEY` is set; run the dry-run snippet above to see the raw LLM response |
| Cert renewal failing | Ensure port 80 is open and nothing else is bound to it when the certbot container runs |
