# Examples

| File | Description |
|------|-------------|
| [`mailagent.starter.yml`](mailagent.starter.yml) | Commented starter template — copy and customize this to create your `mailagent.yml` |
| [`mailagent.minimal.yml`](mailagent.minimal.yml) | Minimal single-inbox config to get started quickly |
| [`mailagent.yml`](mailagent.yml) | Full-featured multi-inbox config with all options demonstrated |
| [`mailagent.test.yml`](mailagent.test.yml) | Test definitions for `mailagent test dry` / `mailagent test live` |
| [`docker-compose.yml`](docker-compose.yml) | Docker Compose stack with mailserver + mailagent |
| [`docker-compose.test.yml`](docker-compose.test.yml) | Test stack with Inbucket for local development |

## Getting started

1. Follow the [setup guide](../docs/setup.md) to get mailagent running
2. See the [configuration reference](../docs/configuration.md) for all available options

## Schema autocomplete

For config schema autocomplete in your editor, add this to the top of your YAML:

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/vrag99/mailagent/main/schema.json
```
