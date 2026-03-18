# mailagent

General-purpose agentic inbox for docker-mailserver.

`mailagent` watches one or more Maildir inboxes, classifies incoming email with LLM providers, and executes workflows (`reply`, `ignore`, `notify`, `webhook`). It is designed to run as a sidecar container in an existing docker-mailserver stack.

## What you get

- Multi-inbox support in one config file (`mailagent.yml`)
- Named provider configs (`openai`, `anthropic`, `gemini`, `openrouter`, `groq`)
- LLM-first classification with keyword fallback
- Per-inbox workflow pipelines (first match wins)
- JSON Schema autocomplete for editor-driven config authoring
- CLI for daemon, validation, dry-run testing, and schema output

## Quick start

Use the published image with docker-mailserver:

```yaml
services:
  mailserver:
    image: ghcr.io/docker-mailserver/docker-mailserver:latest
    # ... your existing config

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

Then:

1. Copy `examples/mailagent.minimal.yml` to `mailagent.yml` and configure your inboxes and workflows.
2. Create a `mailagent.env` file with the secrets referenced in your config:
   ```env
   GROQ_API_KEY=gsk_...
   ANTHROPIC_API_KEY=sk-ant-...
   MAIL_PASSWORD=your-mailbox-password
   # Add any other ${VAR} values used in mailagent.yml
   ```
3. Start the stack and check logs:
   ```bash
   docker compose up -d
   docker compose logs -f mailagent
   ```

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

Examples:

```bash
mailagent run
mailagent run -c ./mailagent.yml
mailagent validate -c ./mailagent.yml
mailagent test ./some-email.eml -c ./mailagent.yml
mailagent schema > schema.json
```

### `mailagent validate`

- Loads YAML config
- Interpolates env vars (`${VAR}` and `${VAR:-default}`)
- Validates against `schema.json`
- Applies extra semantic checks (provider refs, fallback placement, duplicates)
- Warns when maildir paths are missing (does not fail)

Returns exit code `0` on success, `1` on error.

### `mailagent test <file.eml>`

- Parses a single `.eml`
- Runs classification (real LLM call if configured)
- Prints selected workflow + action preview
- Does not send email or call webhooks

### `mailagent schema`

Prints the full JSON Schema to stdout for local editor setup.

## Schema-powered autocomplete

Default schema file is at repo root: `schema.json`.

In YAML files:

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

## Configuration model

Top-level sections:

- `providers`: named provider configs
- `defaults`: default providers, prompt, blocklist
- `inboxes`: per-inbox credentials + workflows
- `settings`: runtime behavior

Key behavior:

- Workflows are inbox-local and evaluated in order
- `match.intent: default` is catch-all fallback
- `keywords.any` / `keywords.all` are fallback matcher if LLM fails
- Global + inbox blocklists are merged
- Global + inbox system prompts are merged

See full examples:

- `examples/mailagent.yml`
- `examples/mailagent.minimal.yml`
- `examples/docker-compose.yml`

Sample addresses in examples use `you@example.com`.

## Build and run locally

```bash
pip install -e .
mailagent validate -c ./examples/mailagent.minimal.yml
```

Docker build:

```bash
docker build -t mailagent/mailagent:local .
```

## Testing

Run unit tests:

```bash
pytest -q
```

Test coverage includes:

- config loading + schema validation
- provider adapters + retry/timeout paths
- parser fixtures (plain/html/multipart/non-utf8/mailing-list)
- classifier fallback behavior
- workflows execution behavior (dry-run and delivery path)
- watcher event routing
- state idempotency and pruning

## Project structure

```text
mailagent/
├── Dockerfile
├── pyproject.toml
├── README.md
├── schema.json
├── examples/
│   ├── mailagent.yml
│   ├── mailagent.minimal.yml
│   └── docker-compose.yml
├── src/
│   └── mailagent/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── watcher.py
│       ├── parser.py
│       ├── classifier.py
│       ├── workflows.py
│       ├── mailer.py
│       ├── state.py
│       ├── schema.json
│       ├── providers/
│       │   ├── __init__.py
│       │   ├── openai.py
│       │   ├── anthropic.py
│       │   ├── gemini.py
│       │   ├── openrouter.py
│       │   └── groq.py
│       └── utils/
│           ├── __init__.py
│           ├── logging.py
│           └── env.py
└── tests/
    ├── conftest.py
    ├── fixtures/
    │   ├── plain_text.eml
    │   ├── html_only.eml
    │   ├── multipart.eml
    │   ├── non_utf8.eml
    │   └── mailing_list.eml
    ├── test_config.py
    ├── test_parser.py
    ├── test_classifier.py
    ├── test_workflows.py
    ├── test_providers.py
    ├── test_state.py
    └── test_watcher.py
```
