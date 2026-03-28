# Setup Guide

## Table of Contents

- [Path A: Starting from scratch](#path-a-starting-from-scratch)
- [Path B: Existing docker-mailserver](#path-b-existing-docker-mailserver)
- [Next steps](#next-steps)

## Path A: Starting from scratch

This path walks you through setting up a full mail server with mailagent from zero.

### 1. Prerequisites

- A VPS with a public IP (any cloud provider works)
- A domain name with access to DNS settings
- Docker and Docker Compose installed on the VPS

### 2. Provision a VPS

Any Linux VPS with Docker will work. See the [docker-mailserver documentation](https://docker-mailserver.github.io/docker-mailserver/latest/introduction/) for detailed requirements and recommendations.

### 3. Configure DNS

Set up the following DNS records for your domain:

| Type | Name | Value |
|------|------|-------|
| A | `mail.example.com` | Your VPS IP |
| MX | `example.com` | `mail.example.com` |

You will also need SPF, DKIM, and DMARC records. See the [docker-mailserver DNS documentation](https://docker-mailserver.github.io/docker-mailserver/latest/config/best-practices/dkim_dmarc_spf/) for complete instructions.

### 4. Run the setup wizard

The interactive setup wizard downloads docker-mailserver files, configures SSL, creates mailboxes, sets up AI providers, and generates a starter `mailagent.yml`.

```bash
wget -qO setup.sh https://raw.githubusercontent.com/vrag99/mailagent/main/setup.sh && bash setup.sh
```

The wizard will guide you through:
- Downloading the docker-mailserver compose file and environment config
- Configuring SSL certificates (Let's Encrypt recommended)
- Creating email accounts
- Selecting and configuring LLM providers
- Generating a starter `mailagent.yml` with your first inbox and workflows

### 5. Configure mailagent.yml

Customize the generated `mailagent.yml` to define your inboxes and workflows. See the [configuration reference](configuration.md) for all available options.

### 6. Start the stack

```bash
docker compose up -d
docker compose logs -f mailagent
```

### 7. (Optional) Enable the REST API

If you want to manage inboxes and send emails programmatically, start the API service and create an API key:

```bash
docker compose up -d mailagent-api

# Create an API key
docker compose exec mailagent-api mailagent api-key create --name myapp
```

See the [REST API reference](api.md) for the full endpoint list.

## Path B: Existing docker-mailserver

Already running docker-mailserver? Add mailagent as a sidecar service.

### 1. Add mailagent to your compose file

Add the following service to your existing `docker-compose.yml`:

```yaml
  mailagent:
    image: ghcr.io/vrag99/mailagent:latest
    container_name: mailagent
    env_file: ./mailagent.env
    volumes:
      # Mail data — read-only access to your existing maildir
      - ./docker-data/dms/mail-data/:/var/mail/:ro
      # Config — writable so the API service can update it and the daemon hot-reloads
      - ./mailagent.yml:/app/config.yml
      # State — persistent storage for processed-email tracking
      - ./mailagent-data/:/app/data/
    depends_on:
      mailserver:
        condition: service_healthy
    restart: unless-stopped

  # Optional: REST API for inbox/workflow management
  mailagent-api:
    image: ghcr.io/vrag99/mailagent:latest
    container_name: mailagent-api
    command: mailagent serve -c /app/config.yml
    env_file: ./mailagent.env
    ports:
      - "8000:8000"
    volumes:
      - ./mailagent.yml:/app/config.yml
      - ./mailagent-data/:/app/data/
      - ./docker-data/dms/config/:/etc/dms/config/
    depends_on:
      mailserver:
        condition: service_healthy
    restart: unless-stopped
```

> Adjust the mail-data and DMS config volume paths if your docker-mailserver stores files elsewhere.

### 2. Create mailagent.yml

Download the starter template and customize it:

```bash
wget -qO mailagent.yml https://raw.githubusercontent.com/vrag99/mailagent/main/examples/mailagent.starter.yml
```

Edit `mailagent.yml` to configure your inboxes and workflows. See the [configuration reference](configuration.md) for all available options.

### 3. Create mailagent.env

Create a `mailagent.env` file with the secrets referenced in your config via `${VAR}` interpolation:

```env
GROQ_API_KEY=gsk_...
ANTHROPIC_API_KEY=sk-ant-...
MAIL_PASSWORD_1=your-mailbox-password
# Add any other ${VAR} values used in mailagent.yml
```

### 4. Start mailagent

```bash
docker compose up -d mailagent
docker compose logs -f mailagent
```

### 5. (Optional) Enable the REST API

Start the API service and create an API key:

```bash
docker compose up -d mailagent-api

# Create an API key
docker compose exec mailagent-api mailagent api-key create --name myapp
```

See the [REST API reference](api.md) for the full endpoint list.

## Next steps

- [Configuration reference](configuration.md) — full documentation of all config options
- [REST API reference](api.md) — full API endpoint documentation
- [Examples](../examples/) — sample configs for common setups
- Run `mailagent validate -c ./mailagent.yml` to check your config
- Run `mailagent test ./email.eml -c ./mailagent.yml` to dry-run an email through the pipeline
