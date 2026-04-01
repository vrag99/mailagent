# REST API Reference

mailagent includes an optional REST API for managing inboxes, providers, workflows, and sending emails programmatically. It runs as a separate container using the same Docker image.

## How it works

Both containers use the same `ghcr.io/vrag99/mailagent` image:

- **Daemon** — runs `mailagent run`, watches Maildir, processes emails
- **API** — runs `mailagent serve`, exposes the HTTP API

Config sync happens via file polling: the API writes changes to `mailagent.yml`, and the daemon polls the file's mtime every 5 seconds and hot-reloads on change. No inter-container signaling is needed.

## Docker Compose setup

Add the API service alongside the daemon:

```yaml
services:
  mailagent:
    image: ghcr.io/vrag99/mailagent:latest
    env_file: ./mailagent.env
    volumes:
      - ./docker-data/dms/mail-data/:/var/mail/:ro
      - ./mailagent.yml:/app/config.yml   # writable — daemon hot-reloads on API changes
      - ./mailagent-data/:/app/data/
    restart: unless-stopped

  mailagent-api:
    image: ghcr.io/vrag99/mailagent:latest
    command: mailagent serve -c /app/config.yml
    env_file: ./mailagent.env
    ports:
      - "8000:8000"
    volumes:
      - ./mailagent.yml:/app/config.yml
      - ./mailagent-data/:/app/data/
      - ./docker-data/dms/config/:/etc/dms/config/   # for mailbox provisioning
    restart: unless-stopped
```

## Running locally

```bash
# Start the server
uv run mailagent serve -c path/to/mailagent.yml

# Options
uv run mailagent serve --help
#  -c, --config PATH     Config file path
#  --host TEXT           Bind host (default: 0.0.0.0)
#  --port INTEGER        Bind port (default: 8000)
#  --api-keys PATH       API keys file (default: data/api-keys.yml)
#  --dms-config PATH     docker-mailserver config dir (default: /etc/dms/config)
```

## Authentication

All endpoints (except `GET /health`) require a Bearer token.

### Managing API keys

```bash
# Create a key — prints the raw key once; save it now
mailagent api-key create --name myapp
# ma_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# List keys — shows name, creation date, and the first 12 chars of the hash
mailagent api-key list

# Revoke a key — pass the hash prefix shown by `api-key list`
mailagent api-key revoke <hash_prefix>
```

Keys are stored as SHA-256 hashes in `data/api-keys.yml`. The raw key is shown only once on creation. If no keys file exists, auth is not enforced (first-run convenience).

### Sending authenticated requests

Pass the key as a Bearer token in the `Authorization` header:

```bash
Authorization: Bearer ma_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

```bash
curl -H "Authorization: Bearer ma_<your-key>" http://localhost:8000/api/inboxes
```

Any request to a protected endpoint without a valid key returns `401 Unauthorized`.

## Endpoints

### Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | no | Returns `{"status": "ok"}` |

### Inboxes

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/inboxes` | yes | List all inboxes |
| `GET` | `/api/inboxes/{address}` | yes | Get a single inbox |
| `POST` | `/api/inboxes` | yes | Create an inbox (also provisions the mailbox) |
| `PATCH` | `/api/inboxes/{address}` | yes | Update inbox fields |
| `DELETE` | `/api/inboxes/{address}` | yes | Delete an inbox and deprovision the mailbox |

`POST /api/inboxes` returns `201 Created`. `DELETE` returns `204 No Content`.

### Workflows

Workflows are nested under their inbox.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/inboxes/{address}/workflows` | yes | List workflows for an inbox |
| `GET` | `/api/inboxes/{address}/workflows/{name}` | yes | Get a single workflow |
| `POST` | `/api/inboxes/{address}/workflows` | yes | Add a workflow |
| `PUT` | `/api/inboxes/{address}/workflows/{name}` | yes | Replace a workflow |
| `DELETE` | `/api/inboxes/{address}/workflows/{name}` | yes | Remove a workflow |

`POST` returns `201 Created`. `DELETE` returns `204 No Content`.

### Providers

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/providers` | yes | List all providers |
| `GET` | `/api/providers/{name}` | yes | Get a single provider |
| `POST` | `/api/providers/{name}` | yes | Create a provider |
| `PUT` | `/api/providers/{name}` | yes | Replace a provider |
| `DELETE` | `/api/providers/{name}` | yes | Delete a provider |

`POST` returns `201 Created`. `DELETE` returns `204 No Content`.

Deleting a provider that is referenced by an inbox or set as a default returns `409 Conflict`.

### Emails

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/emails/send` | yes | Compose and send a fresh email |

The sent email is saved to the inbox's Sent folder via IMAP.

#### Request body

```json
{
  "from_address": "alice@example.com",
  "to": "bob@example.com",
  "subject": "Hello",
  "body": "Hi Bob,\n\nJust checking in.\n\nAlice"
}
```

#### Response

```json
{
  "message_id": "<abc123@example.com>"
}
```

## Example: create an inbox

```bash
curl -X POST http://localhost:8000/api/inboxes \
  -H "Authorization: Bearer <key>" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "support@example.com",
    "name": "Support Team",
    "credentials": {"password": "s3cr3t"},
    "classify_provider": "fast",
    "reply_provider": "smart",
    "workflows": [
      {
        "name": "fallback",
        "match": {"intent": "default"},
        "action": {"type": "ignore"}
      }
    ]
  }'
```

## Example: send an email

```bash
curl -X POST http://localhost:8000/api/emails/send \
  -H "Authorization: Bearer <key>" \
  -H "Content-Type: application/json" \
  -d '{
    "from_address": "alice@example.com",
    "to": "bob@example.com",
    "subject": "Following up",
    "body": "Hi Bob, just wanted to follow up on our conversation."
  }'
```
