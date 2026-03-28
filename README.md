<h1 align="center">mailagent</h1>
<p align="center"><em>Your inbox, on autopilot.</em></p>

<p align="center">
  <a href="https://github.com/vrag99/mailagent/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License"></a>
  <a href="https://pypi.org/project/docker-mailagent/"><img src="https://img.shields.io/pypi/v/docker-mailagent" alt="PyPI version"></a>
  <a href="https://pypi.org/project/docker-mailagent/"><img src="https://img.shields.io/pypi/pyversions/docker-mailagent" alt="Python versions"></a>
  <a href="https://ghcr.io/vrag99/mailagent"><img src="https://img.shields.io/badge/ghcr.io-vrag99%2Fmailagent-blue" alt="Docker image"></a>
</p>

> [!WARNING]
> 🚧 **Under active development** — expect rough edges, breaking changes, and bugs. Contributions and issue reports welcome!

LLM-powered email agent that watches Maildir inboxes, classifies mail, and executes workflows. Docker sidecar for [docker-mailserver](https://github.com/docker-mailserver/docker-mailserver).

## Features

- [x] Multi-inbox support with 5 LLM providers (OpenAI, Anthropic, Gemini, OpenRouter, Groq)
- [x] LLM classification with keyword fallback
- [x] 4 action types: `reply`, `ignore`, `notify`, `webhook` — composable
- [x] Smart SMTP replies with threading, sent folder sync, and message flagging
- [x] Env var interpolation, JSON Schema autocomplete, global + per-inbox config
- [x] inotify watching, catch-up on restart, debounce, idempotent state
- [x] CLI (`run`, `validate`, `test`, `schema`) with rich output
- [x] Thread awareness
- [x] REST API for inbox/provider/workflow CRUD and sending emails
- [ ] Web dashboard for monitoring and config management
- [ ] Calendar-aware scheduling actions
- [ ] Plugin system for custom action types
... and more to come(based on feedback and bugs)

## Quick start

Setting up a **new mail server**? Follow [Path A in the setup guide](docs/setup.md#path-a-starting-from-scratch).

Already running **docker-mailserver**? Follow [Path B in the setup guide](docs/setup.md#path-b-existing-docker-mailserver).

Here's a taste of what the stack looks like:

```yaml
services:
  mailserver:
    image: ghcr.io/docker-mailserver/docker-mailserver:latest
    # ... your config

  mailagent:
    image: ghcr.io/vrag99/mailagent:latest
    env_file: ./mailagent.env
    volumes:
      - ./docker-data/dms/mail-data/:/var/mail/:ro
      - ./mailagent.yml:/app/config.yml   # writable — daemon hot-reloads on API changes
      - ./mailagent-data/:/app/data/
    depends_on:
      mailserver:
        condition: service_healthy
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
    depends_on:
      mailserver:
        condition: service_healthy
    restart: unless-stopped
```

1. Create `mailagent.yml` from the [starter template](examples/mailagent.starter.yml)
2. Create `mailagent.env` with your API keys and secrets
3. `docker compose up -d`

## CLI

```bash
uv pip install docker-mailagent
```

```text
Usage: mailagent <command> [options]

Commands:
  run         Start the mail agent daemon (default)
  validate    Validate the config file and exit
  test        Dry-run a .eml file through the pipeline
  schema      Print the JSON Schema to stdout
  serve       Start the REST API server
  api-key     Manage API keys (create, list, revoke)

Options:
  -c, --config PATH    Config file path (default: /app/config.yml)
  -v, --verbose        Enable debug logging
```

```bash
mailagent validate -c ./mailagent.yml
mailagent test ./some-email.eml -c ./mailagent.yml
mailagent schema > schema.json

# Start the REST API server
mailagent serve -c ./mailagent.yml --port 8000

# Manage API keys
mailagent api-key create --name myapp   # prints key once — save it
mailagent api-key list                  # shows name + hash prefix
mailagent api-key revoke <hash_prefix>  # use hash prefix from list
```

## Schema autocomplete

Add to the top of your YAML file:

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/vrag99/mailagent/main/schema.json
```

VS Code mapping:

```json
{
  "yaml.schemas": {
    "https://raw.githubusercontent.com/vrag99/mailagent/main/schema.json": "mailagent.yml"
  }
}
```

## Configuration

mailagent is configured via a single `mailagent.yml` file with four top-level sections: `providers`, `defaults`, `inboxes`, and `settings`. Workflows are inbox-local and evaluated in order (first match wins).

See the full [configuration reference](docs/configuration.md) and [examples](examples/).

## Development

```bash
uv sync --dev
uv run pytest -q
docker build -t mailagent/mailagent:local .
```

## License

[MIT](LICENSE)
