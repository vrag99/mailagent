#!/usr/bin/env bash
# Obtain (first run) or renew Let's Encrypt certificates for mail.garv.me.
#
# Uses the standalone HTTP-01 challenge, so port 80 must be reachable.
# Run manually for the first cert; a cron job handles renewals.
#
# Usage:
#   ./scripts/certbot-renew.sh            # obtain / renew
#   CERTBOT_STAGING=1 ./scripts/certbot-renew.sh  # test with staging CA

set -euo pipefail

DOMAIN="${DOMAIN:-mail.garv.me}"
EMAIL="${CERTBOT_EMAIL:-}"        # set in env or edit below
CERT_DIR="./docker-data/certbot/certs"
WEBROOT_DIR="./docker-data/certbot/webroot"

STAGING_FLAG=""
if [[ "${CERTBOT_STAGING:-0}" == "1" ]]; then
    STAGING_FLAG="--staging"
    echo "[certbot] Using Let's Encrypt staging environment"
fi

if [[ -z "$EMAIL" ]]; then
    echo "Error: CERTBOT_EMAIL env var is not set." >&2
    exit 1
fi

mkdir -p "$CERT_DIR" "$WEBROOT_DIR"

# ---------------------------------------------------------------------------
# Check whether a certificate already exists and is close to expiry (< 30d).
# If it is still valid, skip unless FORCE_RENEW=1.
# ---------------------------------------------------------------------------
LIVE_CERT="$CERT_DIR/live/$DOMAIN/cert.pem"

if [[ -f "$LIVE_CERT" && "${FORCE_RENEW:-0}" != "1" ]]; then
    EXPIRY=$(openssl x509 -enddate -noout -in "$LIVE_CERT" | cut -d= -f2)
    EXPIRY_EPOCH=$(date -d "$EXPIRY" +%s 2>/dev/null || date -jf "%b %d %T %Y %Z" "$EXPIRY" +%s)
    NOW_EPOCH=$(date +%s)
    DAYS_LEFT=$(( (EXPIRY_EPOCH - NOW_EPOCH) / 86400 ))

    if (( DAYS_LEFT > 30 )); then
        echo "[certbot] Certificate valid for ${DAYS_LEFT} more days — skipping renewal."
        exit 0
    fi
    echo "[certbot] Certificate expires in ${DAYS_LEFT} days — renewing."
fi

# ---------------------------------------------------------------------------
# Stop services that hold port 80 (adjust if you run a reverse proxy).
# Comment out if port 80 is already served by a webserver you control.
# ---------------------------------------------------------------------------
# docker compose stop mailserver 2>/dev/null || true

# ---------------------------------------------------------------------------
# Run certbot in a temporary container (no permanent certbot install needed).
# ---------------------------------------------------------------------------
docker run --rm \
    -v "$(pwd)/$CERT_DIR:/etc/letsencrypt" \
    -v "$(pwd)/$WEBROOT_DIR:/var/www/certbot" \
    -p 80:80 \
    certbot/certbot certonly \
        --standalone \
        --non-interactive \
        --agree-tos \
        --email "$EMAIL" \
        --domains "$DOMAIN" \
        --cert-path "/etc/letsencrypt/live/$DOMAIN/cert.pem" \
        --key-path "/etc/letsencrypt/live/$DOMAIN/privkey.pem" \
        --fullchain-path "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" \
        --config-dir "/etc/letsencrypt" \
        $STAGING_FLAG

echo "[certbot] Certificate obtained/renewed for $DOMAIN."

# ---------------------------------------------------------------------------
# Restart the mailserver so it picks up the new certificate.
# ---------------------------------------------------------------------------
docker compose restart mailserver
echo "[certbot] mailserver restarted."
