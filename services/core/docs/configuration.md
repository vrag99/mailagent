# mailagent YAML Configuration Reference

This document describes every field in `mailagent.yml`. Use it to write valid configuration files from scratch.

The config file has four top-level sections: `providers`, `defaults`, `inboxes`, and `settings`.

```yaml
providers: { ... }   # required — LLM provider definitions
defaults:  { ... }   # required — global defaults
inboxes:   [ ... ]   # required — at least one inbox
settings:  { ... }   # optional — runtime tuning
```

## Environment Variable Substitution

Any string value in the config can reference environment variables. Variables are loaded from the `.env` file or shell environment at startup.

| Syntax | Behavior |
|--------|----------|
| `${VAR_NAME}` | Replaced with the value of `VAR_NAME`. Fails if unset. |
| `${VAR_NAME:-fallback}` | Replaced with `VAR_NAME` if set, otherwise uses `fallback`. |

Variable names must match `[A-Z_][A-Z0-9_]*`.

Use this for secrets (API keys, passwords, webhook tokens) so they stay out of the YAML file.

```yaml
api_key: ${GROQ_API_KEY}
password: ${MAIL_PASSWORD:-changeme}
```


## 1. Providers

Defines the LLM backends mailagent can use. You must define at least one provider. The key (e.g. `fast`, `smart`) is an arbitrary label you reference elsewhere.

```yaml
providers:
  <name>:
    type: <string>          # required
    model: <string>         # required
    api_key: <string>       # required (use ${ENV_VAR})
    base_url: <string>      # optional
    timeout: <integer>      # optional, default: 30
    retries: <integer>      # optional, default: 1
    http_referer: <string>  # optional (openrouter only)
    x_title: <string>       # optional (openrouter only)
```

### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `type` | string | yes | — | One of: `groq`, `openai`, `anthropic`, `gemini`, `openrouter` |
| `model` | string | yes | — | Model identifier (e.g. `llama-3.3-70b-versatile`, `gpt-4o`, `claude-sonnet-4-20250514`, `gemini-2.5-flash`, `google/gemini-2.5-flash`) |
| `api_key` | string | yes | — | API key. Use `${ENV_VAR}` syntax. |
| `base_url` | string (URI) | no | — | Override the API endpoint. Useful for proxies or OpenAI-compatible servers. |
| `timeout` | integer | no | 30 | HTTP timeout in seconds (minimum: 1). Falls back to `settings.llm_timeout_seconds` if not set. |
| `retries` | integer | no | 1 | Retry count on timeout or 5xx (minimum: 0). |
| `http_referer` | string (URI) | no | — | OpenRouter `HTTP-Referer` attribution header. |
| `x_title` | string | no | — | OpenRouter `X-Title` attribution header. |

### Example

```yaml
providers:
  fast:
    type: groq
    model: llama-3.3-70b-versatile
    api_key: ${GROQ_API_KEY}

  smart:
    type: anthropic
    model: claude-sonnet-4-20250514
    api_key: ${ANTHROPIC_API_KEY}
    timeout: 60

  router:
    type: openrouter
    model: anthropic/claude-sonnet-4
    api_key: ${OPENROUTER_API_KEY}
    http_referer: https://example.com
    x_title: mailagent
```

### Common provider/model pairings

| type | env key | suggested model |
|------|---------|-----------------|
| `groq` | `GROQ_API_KEY` | `llama-3.3-70b-versatile` |
| `openai` | `OPENAI_API_KEY` | `gpt-4o` |
| `anthropic` | `ANTHROPIC_API_KEY` | `claude-sonnet-4-20250514` |
| `gemini` | `GEMINI_API_KEY` | `gemini-2.5-flash` |
| `openrouter` | `OPENROUTER_API_KEY` | `google/gemini-2.5-flash` |


## 2. Defaults

Global defaults applied to all inboxes unless overridden at the inbox level.

```yaml
defaults:
  classify_provider: <string>  # required
  reply_provider: <string>     # required
  system_prompt: <string>      # optional
  blocklist:                   # optional
    from_patterns: [...]
    headers: [...]
```

### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `classify_provider` | string | yes | — | Name of a provider from the `providers` section. Used to classify incoming emails into workflows. |
| `reply_provider` | string | yes | — | Name of a provider from the `providers` section. Used to generate email replies. |
| `system_prompt` | string | no | `"You are a helpful email assistant."` | System prompt prepended to all LLM calls. Inbox-level prompts are appended after this. |
| `blocklist` | object | no | empty | Global blocklist. See [Blocklist](#blocklist) below. |

### Example

```yaml
defaults:
  classify_provider: fast
  reply_provider: smart
  system_prompt: |
    You are a helpful email assistant.
  blocklist:
    from_patterns:
      - "noreply@"
      - "no-reply@"
      - "mailer-daemon@"
    headers:
      - "List-Unsubscribe"
      - "Precedence: bulk"
```


## 3. Inboxes

An array of email inboxes to monitor. At least one inbox is required. Each inbox has its own workflows and can override provider/prompt/blocklist settings.

```yaml
inboxes:
  - address: <string>              # required
    name: <string>                 # optional
    credentials:
      password: <string>           # required
    classify_provider: <string>    # optional (overrides defaults)
    reply_provider: <string>       # optional (overrides defaults)
    system_prompt: <string>        # optional (appended to defaults)
    blocklist: { ... }             # optional (merged with defaults)
    workflows: [ ... ]             # required, at least one
```

### Inbox Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `address` | string (email) | yes | — | The email address to monitor (e.g. `you@example.com`). Must be unique across inboxes (case-insensitive). |
| `name` | string | no | — | Display name for this inbox (e.g. `Jane Doe`). Used as the From name when sending replies. |
| `credentials.password` | string | yes | — | Mailbox password. Use `${ENV_VAR}` syntax. |
| `classify_provider` | string | no | `defaults.classify_provider` | Override the classification LLM for this inbox. Must reference a defined provider. |
| `reply_provider` | string | no | `defaults.reply_provider` | Override the reply LLM for this inbox. Must reference a defined provider. |
| `system_prompt` | string | no | — | Inbox-specific system prompt. Appended to `defaults.system_prompt` (both are used). |
| `blocklist` | object | no | — | Inbox-specific blocklist. Merged (concatenated) with `defaults.blocklist`. |
| `workflows` | array | yes | — | Ordered list of workflows. First match wins. Must have at least one entry. |

### Duplicate addresses

Inbox addresses are normalized to lowercase. Duplicate addresses cause a config error.

### Example

```yaml
inboxes:
  - address: alice@example.com
    name: Alice
    credentials:
      password: ${MAIL_PASSWORD_1}
    classify_provider: fast
    reply_provider: smart
    system_prompt: |
      You are Alice's email assistant. Be concise and friendly.
    blocklist:
      from_patterns:
        - "recruiter@"
    workflows:
      - name: meeting-request
        match:
          intent: "requesting a meeting, call, or video chat"
          keywords:
            any: ["meeting", "schedule", "call", "zoom"]
        action:
          type: reply
          prompt: |
            Acknowledge the request and ask for available time slots.
      - name: fallback
        match:
          intent: default
        action:
          type: ignore
```


## 4. Workflows

Each inbox has an ordered list of workflows. When an email arrives, mailagent evaluates workflows top-to-bottom and executes the first match.

```yaml
workflows:
  - name: <string>       # required
    match:
      intent: <string>   # required
      keywords:           # optional
        any: [...]
        all: [...]
    action: { ... }       # required
```

### Workflow Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Identifier for this workflow (unique within the inbox). |
| `match` | object | yes | Matching criteria. See below. |
| `action` | object | yes | What to do when matched. See [Actions](#5-actions). |

### Match

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `match.intent` | string | yes | Natural-language description of what this workflow handles. The LLM uses this to decide if an email fits. Use `"default"` for the catch-all fallback. |
| `match.keywords` | object | no | Hard keyword filters applied BEFORE the LLM. If keywords don't match, the workflow is skipped regardless of intent. |
| `match.keywords.any` | string[] | conditional | At least one keyword must appear in the email subject or body (case-insensitive). |
| `match.keywords.all` | string[] | conditional | All keywords must appear in the email subject or body (case-insensitive). |

If `keywords` is present, at least one of `any` or `all` must be provided. Both can be used together (both conditions must pass).

### Ordering rules

- Workflows are evaluated **top-to-bottom**; the **first match wins**.
- Always place the fallback workflow (`intent: default`) **last**.
- Any workflow after a `default` workflow is unreachable (mailagent warns).
- If no workflow has `intent: default`, mailagent auto-adds an `ignore` fallback and emits a warning.

### Example

```yaml
workflows:
  - name: meeting-request
    match:
      intent: "requesting a meeting, call, or video chat"
      keywords:
        any: ["meeting", "schedule", "call", "sync", "zoom"]
    action:
      type: reply
      prompt: |
        Acknowledge the request and suggest available time slots.

  - name: invoice
    match:
      intent: "invoice, payment request, or billing notification"
      keywords:
        all: ["invoice"]
        any: ["payment", "due", "amount"]
    action:
      type: webhook
      url: ${INVOICE_WEBHOOK_URL}
      method: POST
      payload:
        from: "{{from}}"
        subject: "{{subject}}"
        body: "{{body_truncated}}"

  - name: spam
    match:
      intent: "cold outreach, sales pitch, or marketing"
      keywords:
        any: ["unsubscribe", "opt out", "limited time"]
    action:
      type: ignore

  - name: fallback
    match:
      intent: default
    action:
      type: ignore
```


## 5. Actions

Every workflow has an `action` that determines what happens when the workflow matches.

### Action types

There are four action types: `reply`, `ignore`, `notify`, and `webhook`.


### `type: reply`

Generate an LLM reply and send it to the sender.

```yaml
action:
  type: reply
  prompt: <string>            # required
  also_webhook: <boolean>     # optional, default: false
  webhook_url: <string>       # required if also_webhook is true
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `prompt` | string | yes | — | Instructions for the LLM on how to compose the reply. |
| `also_webhook` | boolean | no | false | Also send a webhook notification after replying. |
| `webhook_url` | string | conditional | — | Required when `also_webhook: true`. URL to POST to. |

```yaml
action:
  type: reply
  prompt: |
    Thank the sender for reaching out and say someone will follow up soon.
    Keep it to 2-3 sentences.
```


### `type: ignore`

Silently skip the email. No fields beyond `type`.

```yaml
action:
  type: ignore
```


### `type: notify`

Send a webhook notification. Optionally also generate and send a reply.

```yaml
action:
  type: notify
  webhook: <string>           # required
  also_reply: <boolean>       # optional, default: false
  prompt: <string>            # required if also_reply is true
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `webhook` | string | yes | — | URL to POST the notification to. Supports `${ENV_VAR}`. |
| `also_reply` | boolean | no | false | Also generate and send a reply to the sender. |
| `prompt` | string | conditional | — | Required when `also_reply: true`. Instructions for the reply. |

The notification payload is automatically built with `from`, `subject`, `date`, and `summary` (first 500 chars of body).

```yaml
action:
  type: notify
  webhook: ${SLACK_WEBHOOK_URL}
  also_reply: true
  prompt: |
    Acknowledge the email and say you will look into it shortly.
```


### `type: webhook`

Call an arbitrary HTTP endpoint with a custom payload.

```yaml
action:
  type: webhook
  url: <string>               # required
  method: <string>            # optional, default: "POST"
  headers: { ... }            # optional
  payload: { ... }            # optional
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `url` | string | yes | — | URL to call. Supports `${ENV_VAR}`. |
| `method` | string | no | `POST` | One of: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`. |
| `headers` | object | no | `{}` | HTTP headers. Values support `${ENV_VAR}`. |
| `payload` | object | no | `{}` | JSON body. Values support `{{template}}` variables (see below). If omitted, a default payload with `from`, `subject`, `date`, `body` is sent. |

```yaml
action:
  type: webhook
  url: ${INVOICE_WEBHOOK_URL}
  method: POST
  headers:
    Authorization: "Bearer ${WEBHOOK_TOKEN}"
    Content-Type: "application/json"
  payload:
    sender: "{{from}}"
    subject: "{{subject}}"
    received: "{{date}}"
    body: "{{body_truncated}}"
```

### Payload template variables

Use `{{variable}}` in payload string values. These are replaced with data from the incoming email at execution time.

| Variable | Description |
|----------|-------------|
| `{{from}}` | Full From header (e.g. `"Jane Doe <jane@example.com>"`) |
| `{{from_email}}` | Bare email address (e.g. `jane@example.com`) |
| `{{to}}` | Full To header |
| `{{subject}}` | Email subject line |
| `{{date}}` | Email date header |
| `{{body}}` | Full plain-text body |
| `{{body_truncated}}` | Body truncated to `settings.classify_body_limit` characters |
| `{{message_id}}` | Email Message-ID header |


## Blocklist

Blocklists skip emails before any LLM call. They can be defined globally in `defaults.blocklist` and per-inbox. Per-inbox blocklists are **merged** (concatenated) with the global one.

```yaml
blocklist:
  from_patterns: [...]   # optional
  headers: [...]         # optional
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `from_patterns` | string[] | `[]` | Case-insensitive substrings matched against the sender address. If any pattern matches, the email is blocked. |
| `headers` | string[] | `[]` | Header names or literal fragments. If the email contains any of these headers/values, it is blocked. |

### Example

```yaml
blocklist:
  from_patterns:
    - "noreply@"
    - "no-reply@"
    - "mailer-daemon@"
    - "notifications@"
  headers:
    - "List-Unsubscribe"
    - "Precedence: bulk"
    - "Precedence: list"
    - "X-Auto-Response-Suppress"
```


## 6. Settings

Optional runtime configuration. All fields have sensible defaults.

```yaml
settings:
  mail_host: <string>              # default: "mailserver"
  catch_up_on_start: <boolean>     # default: true
  debounce_ms: <integer>           # default: 200
  classify_body_limit: <integer>   # default: 2000
  reply_body_limit: <integer>      # default: 8000
  llm_retries: <integer>           # default: 1
  llm_timeout_seconds: <integer>   # default: 30
  data_dir: <string>               # default: "/app/data"
  log_level: <string>              # default: "info"
  max_thread_replies: <integer>    # default: 3
  thread_context_limit: <integer>  # default: 3000
  thread_history_max: <integer>    # default: 5
```

### Fields

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `mail_host` | string | `"mailserver"` | — | IMAP/SMTP hostname. Use `"mailserver"` when running alongside docker-mailserver in the same compose stack. |
| `catch_up_on_start` | boolean | `true` | — | Process emails that arrived while mailagent was stopped. |
| `debounce_ms` | integer | `200` | min: 0 | Delay (ms) after a maildir event before processing. Avoids reading partially-written files. |
| `classify_body_limit` | integer | `2000` | min: 100 | Max characters of email body sent to the LLM for classification. |
| `reply_body_limit` | integer | `8000` | min: 100 | Max characters of email body sent to the LLM for reply generation. |
| `llm_retries` | integer | `1` | min: 0 | Default retry count for LLM calls. Provider-level `retries` overrides this. |
| `llm_timeout_seconds` | integer | `30` | min: 1 | Default HTTP timeout (seconds) for LLM calls. Provider-level `timeout` overrides this. |
| `data_dir` | string | `"/app/data"` | — | Directory for mailagent state files. |
| `log_level` | string | `"info"` | `debug`, `info`, `warning`, `error` | Logging verbosity. |
| `max_thread_replies` | integer | `3` | min: 0 | Maximum number of mailagent replies per email thread. 0 means never reply to thread continuations. |
| `thread_context_limit` | integer | `3000` | min: 0 | Maximum characters of thread history included in reply prompts. |
| `thread_history_max` | integer | `5` | min: 0 | Maximum number of prior messages to fetch via IMAP for thread context. |


## Complete Minimal Example

The smallest valid config: one provider, one inbox, one fallback workflow.

```yaml
providers:
  fast:
    type: groq
    model: llama-3.3-70b-versatile
    api_key: ${GROQ_API_KEY}

defaults:
  classify_provider: fast
  reply_provider: fast

inboxes:
  - address: you@example.com
    credentials:
      password: ${MAIL_PASSWORD}
    workflows:
      - name: fallback
        match:
          intent: default
        action:
          type: ignore

settings:
  mail_host: mailserver
```

## Complete Multi-Inbox Example

Two providers, two inboxes with distinct workflows, custom blocklists, and webhook integrations.

```yaml
providers:
  fast:
    type: groq
    model: llama-3.3-70b-versatile
    api_key: ${GROQ_API_KEY}

  smart:
    type: anthropic
    model: claude-sonnet-4-20250514
    api_key: ${ANTHROPIC_API_KEY}

defaults:
  classify_provider: fast
  reply_provider: smart
  system_prompt: |
    You are a helpful email assistant.
  blocklist:
    from_patterns:
      - "noreply@"
      - "no-reply@"
      - "mailer-daemon@"
    headers:
      - "List-Unsubscribe"
      - "Precedence: bulk"

inboxes:
  - address: alice@example.com
    name: Alice
    credentials:
      password: ${MAIL_PASSWORD_1}
    system_prompt: |
      You are Alice's assistant. Be concise and friendly.
    workflows:
      - name: meeting-request
        match:
          intent: "requesting a meeting, call, or video chat"
          keywords:
            any: ["meeting", "schedule", "call", "zoom"]
        action:
          type: reply
          prompt: |
            Acknowledge the meeting request.
            Suggest a few available afternoon slots this week.

      - name: urgent
        match:
          intent: "urgent request requiring immediate attention"
        action:
          type: notify
          webhook: ${SLACK_WEBHOOK_URL}
          also_reply: true
          prompt: |
            Acknowledge the email and say you will look into it shortly.

      - name: fallback
        match:
          intent: default
        action:
          type: ignore

  - address: support@example.com
    name: Support Team
    credentials:
      password: ${MAIL_PASSWORD_2}
    reply_provider: fast
    workflows:
      - name: bug-report
        match:
          intent: "bug report, error, or something broken"
          keywords:
            any: ["bug", "error", "broken", "crash", "not working"]
        action:
          type: reply
          prompt: |
            Thank the sender for the report.
            Ask for steps to reproduce if not already provided.
          also_webhook: true
          webhook_url: ${BUG_WEBHOOK_URL}

      - name: fallback
        match:
          intent: default
        action:
          type: reply
          prompt: |
            Thank them for reaching out and say someone will follow up soon.

settings:
  mail_host: mailserver
  log_level: info
```


## Validation Errors

These cause mailagent to refuse to start:

- Missing or unset environment variable with no default
- `classify_provider` or `reply_provider` references a provider name not defined in `providers`
- Duplicate inbox addresses
- Missing required fields (`address`, `credentials.password`, `workflows`, etc.)
- Invalid `type` value for a provider or action
- `type: reply` without `prompt`
- `type: notify` without `webhook`
- `type: webhook` without `url`

## Validation Warnings

These are logged but mailagent still starts:

- An inbox has no fallback workflow (`intent: default`) — an `ignore` fallback is auto-added
- A non-default workflow appears after a `default` workflow (unreachable)
- Fallback workflow is not the last entry in the workflows list
