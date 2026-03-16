#!/usr/bin/env bash
# inject-test-email.sh — write a valid .eml into the maildir so the agent picks it up.
# Usage: ./scripts/inject-test-email.sh [subject]
#
# Reads MAIL_USER and MAIL_DOMAIN from agent/.env (or environment).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

# Source agent/.env if present
if [[ -f "$REPO_DIR/agent/.env" ]]; then
  set -a
  source "$REPO_DIR/agent/.env"
  set +a
fi

MAIL_USER="${MAIL_USER:?Set MAIL_USER in agent/.env}"
MAIL_DOMAIN="${MAIL_DOMAIN:?Set MAIL_DOMAIN in agent/.env}"

SUBJECT="${1:-Test email $(date +%s)}"
FILENAME="test-$(date +%s)-$$.eml"
DEST="$REPO_DIR/docker-data/dms/mail-data/$MAIL_DOMAIN/$MAIL_USER/new"

mkdir -p "$DEST"

cat > "$DEST/$FILENAME" <<EOF
From: Alice <alice@external.example>
To: ${MAIL_USER}@${MAIL_DOMAIN}
Subject: ${SUBJECT}
Date: $(date -R 2>/dev/null || date +"%a, %d %b %Y %T %z")
Message-ID: <test-${RANDOM}@external.example>
Content-Type: text/plain; charset=utf-8

Hi,

This is a test email injected via inject-test-email.sh.
Would love to catch up sometime. Are you free for a quick call this week?

Best,
Alice
EOF

echo "Injected: $DEST/$FILENAME"
