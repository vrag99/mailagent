#!/usr/bin/env bash
# setup.sh — first-time setup for vessel
#
# Usage:
#   ./setup.sh                                                      # fully interactive
#   ./setup.sh --email you@example.com --host mail.example.com ...  # mix of flags + prompts
#   ./setup.sh --email you@example.com --password <pass> --host mail.example.com --openrouter-key sk-or-...

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------

usage() {
    echo "Usage: $0 [--email <user@domain>] [--password <password>] [--host <mail.example.com>] [--openrouter-key <sk-or-...>]"
    echo "       All flags are optional — omitted values will be prompted interactively."
    exit 1
}

EMAIL=""
PASSWORD=""
MAIL_HOST=""
OPENROUTER_KEY=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --email)          EMAIL="$2";          shift 2 ;;
        --password)       PASSWORD="$2";       shift 2 ;;
        --host)           MAIL_HOST="$2";      shift 2 ;;
        --openrouter-key) OPENROUTER_KEY="$2"; shift 2 ;;
        --help|-h) usage ;;
        *) echo "Unknown argument: $1"; usage ;;
    esac
done

# ---------------------------------------------------------------------------
# Prompt for any missing values
# ---------------------------------------------------------------------------

if [[ -z "$EMAIL" ]]; then
    read -rp "Mailbox email (e.g. you@example.com): " EMAIL
fi

if [[ -z "$PASSWORD" ]]; then
    read -rsp "Mailbox password: " PASSWORD
    echo ""
fi

if [[ -z "$MAIL_HOST" ]]; then
    read -rp "Mail hostname (e.g. mail.example.com): " MAIL_HOST
fi

if [[ -z "$OPENROUTER_KEY" ]]; then
    read -rsp "OpenRouter API key (sk-or-...): " OPENROUTER_KEY
    echo ""
fi

# Validate
if [[ -z "$EMAIL" || -z "$PASSWORD" || -z "$MAIL_HOST" || -z "$OPENROUTER_KEY" ]]; then
    echo "Error: all four values are required." >&2
    exit 1
fi

# Derive user/domain from email
MAIL_USER="${EMAIL%%@*}"
MAIL_DOMAIN="${EMAIL##*@}"

echo ""
echo "==> Setting up vessel for $EMAIL on $MAIL_HOST"
echo ""

# ---------------------------------------------------------------------------
# Step 1: Update hostname in compose.yaml
# ---------------------------------------------------------------------------
echo "[1/5] Updating hostname in compose.yaml..."
sed -i "s|hostname: .*|hostname: $MAIL_HOST|" compose.yaml
echo "      hostname set to $MAIL_HOST"

# ---------------------------------------------------------------------------
# Step 2: Create agent/.env
# ---------------------------------------------------------------------------
echo "[2/5] Writing agent/.env..."
cp agent/.env.example agent/.env
sed -i "s|^MAIL_DOMAIN=.*|MAIL_DOMAIN=\"$MAIL_DOMAIN\"|" agent/.env
sed -i "s|^MAIL_USER=.*|MAIL_USER=\"$MAIL_USER\"|" agent/.env
sed -i "s|^MAIL_PASSWORD=.*|MAIL_PASSWORD=\"$PASSWORD\"|" agent/.env
sed -i "s|^MAIL_HOST=.*|MAIL_HOST=\"$MAIL_HOST\"|" agent/.env
sed -i "s|^OPENROUTER_API_KEY=.*|OPENROUTER_API_KEY=\"$OPENROUTER_KEY\"|" agent/.env
echo "      agent/.env written"

# ---------------------------------------------------------------------------
# Step 3: Update inbox in agent/config.yml
# ---------------------------------------------------------------------------
echo "[3/5] Updating inbox in agent/config.yml..."
sed -i "s|^inbox: .*|inbox: $EMAIL|" agent/config.yml
echo "      inbox set to $EMAIL"

# ---------------------------------------------------------------------------
# Step 4: Start mailserver and create the first mailbox
# ---------------------------------------------------------------------------
echo "[4/5] Creating mailbox"
cp mailserver.env.example mailserver.env
docker compose run --rm mailserver setup email add "$EMAIL" "$PASSWORD"
echo "      Mailbox created."

# ---------------------------------------------------------------------------
# Step 5: Obtain TLS certificate
# ---------------------------------------------------------------------------
echo "[5/5] Obtaining TLS certificate for $MAIL_HOST..."
CERTBOT_EMAIL="$EMAIL" DOMAIN="$MAIL_HOST" ./scripts/certbot-renew.sh

# ---------------------------------------------------------------------------
# Done — post-setup instructions
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo " Setup complete!"
echo "============================================================"
echo ""
echo "Before starting, please review two things:"
echo ""
echo "1. MODELS — check agent/.env and confirm the LLM models are"
echo "   what you want:"
echo ""
echo "     CLASSIFY_MODEL=openai/gpt-4.1-mini"
echo "     REPLY_MODEL=google/gemini-3-flash-preview"
echo ""
echo "   Change to any model available on OpenRouter."
echo ""
echo "2. RELAY HOST — if your VPS blocks outbound port 25 (most do),"
echo "   configure a relay (e.g. Mailgun) in mailserver.env:"
echo ""
echo "     DEFAULT_RELAY_HOST=[smtp.mailgun.org]:587"
echo "     RELAY_USER=<mailgun-smtp-user>"
echo "     RELAY_PASSWORD=<mailgun-smtp-password>"
echo ""
echo "   Full relay documentation:"
echo "   https://docker-mailserver.github.io/docker-mailserver/latest/config/environment/#relay-host"
echo ""
echo "Once ready, start everything (Step 5 in README):"
echo ""
echo "     docker compose up -d"
echo "     docker compose logs -f mail-agent"
echo ""
