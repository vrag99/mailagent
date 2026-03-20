<p align="center">
  <a href="https://github.com/vrag99/mailagent/blob/main/LICENSE"><img src="https://img.shields.io/github/license/vrag99/mailagent" alt="License"></a>
  <a href="https://pypi.org/project/docker-mailagent/"><img src="https://img.shields.io/pypi/v/docker-mailagent" alt="PyPI version"></a>
  <a href="https://pypi.org/project/docker-mailagent/"><img src="https://img.shields.io/pypi/pyversions/docker-mailagent" alt="Python versions"></a>
  <a href="https://ghcr.io/vrag99/mailagent"><img src="https://img.shields.io/badge/ghcr.io-vrag99%2Fmailagent-blue" alt="Docker image"></a>
</p>

<h1 align="center">mailagent</h1>
<p align="center"><em>Your inbox, on autopilot.</em></p>

LLM-powered email agent that watches Maildir inboxes, classifies mail, and executes workflows. Docker sidecar for [docker-mailserver](https://github.com/docker-mailserver/docker-mailserver).

## Features

**Inboxes & Providers**
- Multi-inbox support in one config file
- 5 LLM providers: OpenAI, Anthropic, Gemini, OpenRouter, Groq
- LLM-first classification with keyword fallback

**Actions & Workflows**
- 4 action types: `reply`, `ignore`, `notify`, `webhook` with composite actions
- Smart SMTP replies with threading, IMAP sent folder sync, message flagging
- Webhook template variables (`{{from}}`, `{{subject}}`, `{{body_truncated}}`)

**Configuration**
- Global + per-inbox blocklists and system prompts
- Env var interpolation (`${VAR}`, `${VAR:-default}`)
- JSON Schema autocomplete for editor-driven config authoring

**Runtime**
- inotify Maildir watching, catch-up on restart, debounce, idempotent state
- CLI (`run`, `validate`, `test`, `schema`) with rich output
- Docker sidecar deployment, interactive setup wizard

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
      - ./mailagent.yml:/app/config.yml:ro
      - ./mailagent-data/:/app/data/
    depends_on:
      mailserver:
        condition: service_healthy
    restart: unless-stopped
```

1. Create `mailagent.yml` from the [starter template](examples/mailagent.starter.yml)
2. Create `mailagent.env` with your API keys and secrets
3. `docker compose up -d`

## CLI

```text
Usage: mailagent <command> [options]

Commands:
  run         Start the mail agent daemon (default)
  validate    Validate the config file and exit
  test        Dry-run a .eml file through the pipeline
  schema      Print the JSON Schema to stdout

Options:
  -c, --config PATH    Config file path (default: /app/config.yml)
  -v, --verbose        Enable debug logging
```

```bash
mailagent validate -c ./mailagent.yml
mailagent test ./some-email.eml -c ./mailagent.yml
mailagent schema > schema.json
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
pip install -e .
pytest -q
docker build -t mailagent/mailagent:local .
```

## License

[MIT](LICENSE)
