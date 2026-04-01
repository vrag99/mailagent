# Monorepo Refactor — Implementation Notes

## What Was Done and Why

The project was restructured from a flat layout into a multi-service monorepo. The driving motivation was **SDK distribution**: the auto-generated TypeScript client was previously buried inside the web app (`web/lib/sdk/`), making it impossible to share with any other consumer. The refactor makes it an independently addressable package.

A secondary goal was **architectural clarity**: Python business logic files (`classifier.py`, `watcher.py`, etc.) were sitting at the same level as the API and CLI, blurring the dependency boundary. They are now grouped under a `core/` sub-package with enforced import direction.

---

## What Changed

### Directory structure before

```
mailagent/
├── src/mailagent/
│   ├── classifier.py       # business logic — mixed with api/cli
│   ├── workflows.py
│   ├── mailer.py
│   ├── parser.py
│   ├── watcher.py
│   ├── state.py
│   ├── config.py
│   ├── provisioner.py
│   ├── cli.py
│   ├── api/
│   └── providers/
├── tests/
├── web/                    # Next.js app
│   ├── lib/
│   │   ├── sdk/            # generated SDK embedded inside web app
│   │   └── api-client.ts
│   └── openapi.json
├── pyproject.toml
├── uv.lock
└── Dockerfile
```

### Directory structure after

```
mailagent/
├── services/
│   ├── core/               # Python service
│   │   ├── pyproject.toml
│   │   ├── uv.lock
│   │   ├── src/mailagent/
│   │   │   ├── core/       # business logic (new sub-package)
│   │   │   │   ├── __init__.py
│   │   │   │   ├── classifier.py
│   │   │   │   ├── workflows.py
│   │   │   │   ├── mailer.py
│   │   │   │   ├── parser.py
│   │   │   │   ├── watcher.py
│   │   │   │   └── state.py
│   │   │   ├── api/        # FastAPI layer — unchanged
│   │   │   ├── providers/  # LLM providers — unchanged
│   │   │   ├── testing/    # test runner — unchanged
│   │   │   ├── utils/
│   │   │   ├── config.py
│   │   │   ├── provisioner.py
│   │   │   └── cli.py
│   │   └── tests/
│   │
│   └── ui/                 # Next.js web app (moved from web/)
│       ├── lib/
│       │   └── api-client.ts   # now imports from @mailagent/sdk
│       └── package.json
│
├── packages/
│   ├── sdk-ts/             # @mailagent/sdk — independent TS package
│   │   ├── package.json
│   │   ├── openapi.json    # OpenAPI spec lives here
│   │   └── src/            # generated output (committed)
│   │
│   └── sdk-py/             # mailagent-sdk — Python client scaffold
│       ├── pyproject.toml
│       ├── openapi.json
│       └── src/
│
├── docker/
│   ├── Dockerfile.core     # Python service image (was root Dockerfile)
│   └── Dockerfile.ui       # Next.js image (was web/Dockerfile)
│
├── Makefile                # polyglot task runner
├── pnpm-workspace.yaml     # JS workspace: services/ui + packages/sdk-ts
├── package.json            # root JS package (delegates to make)
├── .tool-versions          # pins Node 22.16.0 + Python 3.12.11 for mise/asdf
├── compose.yaml            # updated build contexts
└── .github/workflows/publish.yml  # updated paths
```

---

## How Each Part Was Implemented

### 1. Python package move (`src/` → `services/core/src/`)

Used `git mv` to preserve history:

```
git mv src services/core/src
git mv pyproject.toml services/core/pyproject.toml
git mv uv.lock services/core/uv.lock
git mv tests services/core/tests
git mv schema.json services/core/schema.json
git mv schema.test.json services/core/schema.test.json
git mv examples services/core/examples
git mv scripts services/core/scripts
git mv docs services/core/docs
```

`pyproject.toml` was updated to use `readme = "../../README.md"` since `README.md` lives at the repo root.

### 2. Web app move (`web/` → `services/ui/`)

```
git mv web services/ui
```

No internal file changes needed at this step — the web app's internal relative imports are unaffected.

### 3. Business logic extraction into `core/` sub-package

Six files were moved from `src/mailagent/` into `src/mailagent/core/`:

```
git mv src/mailagent/classifier.py src/mailagent/core/
git mv src/mailagent/workflows.py  src/mailagent/core/
git mv src/mailagent/mailer.py     src/mailagent/core/
git mv src/mailagent/parser.py     src/mailagent/core/
git mv src/mailagent/watcher.py    src/mailagent/core/
git mv src/mailagent/state.py      src/mailagent/core/
```

An empty `core/__init__.py` was created to make it a proper sub-package.

**Import updates in the moved files:**

`parser.py` and `state.py` — no changes (only stdlib imports).

`mailer.py` — no changes (only imports `parser.py`, a sibling).

`classifier.py`:
```python
# before
from .config import Workflow
from .providers import BaseProvider, ProviderError

# after
from ..config import Workflow       # config is now one level up
from ..providers import BaseProvider, ProviderError
```

`workflows.py`:
```python
# before
from .config import Config, InboxConfig, Workflow, WorkflowAction
from .providers import BaseProvider

# after
from ..config import Config, InboxConfig, Workflow, WorkflowAction
from ..providers import BaseProvider
```

`watcher.py`:
```python
# before
from .config import Config, ConfigError, InboxConfig, load_config
from .providers import BaseProvider, get_provider

# after
from ..config import Config, ConfigError, InboxConfig, load_config
from ..providers import BaseProvider, get_provider
```

**Import updates in callers:**

`cli.py`:
```python
# before
from .classifier import classify
from .parser import parse
from .watcher import build_provider, maildir_new_path, run as run_watcher
from .workflows import execute

# after
from .core.classifier import classify
from .core.parser import parse
from .core.watcher import build_provider, maildir_new_path, run as run_watcher
from .core.workflows import execute
```

`api/routes/emails.py`:
```python
# before
from ...mailer import save_to_sent, send_email

# after
from ...core.mailer import save_to_sent, send_email
```

`testing/runner.py` — all business logic imports prefixed with `core.`.

**Test files** — all `from mailagent.classifier` → `from mailagent.core.classifier`, etc. Also `patch("mailagent.mailer.")` → `patch("mailagent.core.mailer.")` in mock targets.

### 4. TypeScript SDK extracted to `packages/sdk-ts/`

The generated SDK files (`client.gen.ts`, `sdk.gen.ts`, `types.gen.ts`, `index.ts`, `client/`, `core/`) were moved from `services/ui/lib/sdk/` to `packages/sdk-ts/src/`.

`openapi.json` was copied to `packages/sdk-ts/openapi.json` (the spec now lives with the SDK, not the UI).

`packages/sdk-ts/package.json` declares the package as `@mailagent/sdk` with these exports:
```json
{
  "name": "@mailagent/sdk",
  "exports": {
    ".":         "./src/index.ts",
    "./client":  "./src/client.gen.ts",
    "./types":   "./src/types.gen.ts"
  }
}
```

`services/ui/package.json` was updated:
- Added `"@mailagent/sdk": "workspace:*"` as a dependency
- Removed `@hey-api/client-fetch` (it's now a dep of the SDK package)
- Removed `@hey-api/openapi-ts` devDep (moved to SDK package)
- Removed `generate:schema`, `generate:sdk`, `generate` scripts (moved to `Makefile`)

`services/ui/lib/api-client.ts` imports updated:
```typescript
// before
import { client } from "./sdk/client.gen";
import { ... } from "./sdk/sdk.gen";
import type { ... } from "./sdk/types.gen";

// after
import { client } from "@mailagent/sdk/client";
import { ... } from "@mailagent/sdk";
import type { ... } from "@mailagent/sdk/types";
```

### 5. Python SDK scaffold (`packages/sdk-py/`)

Created `packages/sdk-py/pyproject.toml` (package name: `mailagent-sdk`) and a placeholder `src/mailagent_sdk/__init__.py`. The `openapi.json` spec is co-located. Running `make generate-sdk-py` will populate `src/` using `openapi-python-client`.

### 6. Docker

`docker/Dockerfile.core` — identical to the old root `Dockerfile` except build context is now `services/core/` (so all `COPY` paths are relative to that directory, unchanged from before).

`docker/Dockerfile.ui` — multi-stage build with the repo root as context so it can access both `packages/sdk-ts/` and `services/ui/`. The build installs workspace deps, copies both packages, builds Next.js in `services/ui/`, and produces a standalone output.

`compose.yaml` updated:
```yaml
# mailagent / mailagent-api
build:
  context: ./services/core
  dockerfile: ../../docker/Dockerfile.core

# mailagent-web
build:
  context: .
  dockerfile: docker/Dockerfile.ui
```

### 7. Makefile

Single entry point for all cross-language operations:

```makefile
make dev-core        # uv run mailagent serve
make dev-ui          # pnpm dev in services/ui
make generate        # generate-schema + generate-sdk-ts + generate-sdk-py
make generate-schema # extract OpenAPI JSON from FastAPI app
make generate-sdk-ts # run openapi-ts against packages/sdk-ts/openapi.json
make generate-sdk-py # run openapi-python-client against packages/sdk-py/openapi.json
make test            # uv run pytest in services/core
make lint            # ruff + eslint
make build           # docker build for both images
make help            # show all targets with descriptions
```

### 8. pnpm workspace

`pnpm-workspace.yaml` at repo root:
```yaml
packages:
  - "services/ui"
  - "packages/sdk-ts"
```

Running `pnpm install` at the repo root resolves `@mailagent/sdk: workspace:*` in `services/ui` to the local `packages/sdk-ts` package.

---

## Verification Steps

All commands run from the **repo root** (`/Users/vu1k4n/code/projects/mailagent`) unless noted.

### Python tests

```bash
make test
# Expected: 60 passed, 1 skipped
```

### CLI entrypoint

```bash
cd services/core
uv run mailagent --help
# Expected: usage: mailagent [-h] {run,validate,test,schema,serve,api-key}
```

### TypeScript typecheck (verifies SDK imports resolve correctly)

```bash
cd services/ui
pnpm typecheck
# Expected: no output (clean exit)
```

### Workspace dependency resolution

```bash
# From repo root
pnpm install
# Then check services/ui resolves @mailagent/sdk to the local package
cat services/ui/node_modules/@mailagent/sdk/src/index.ts | head -5
# Expected: file contents from packages/sdk-ts/src/index.ts
```

### SDK generation (TypeScript)

```bash
# Requires the API server to be importable
make generate-schema
# Expected: packages/sdk-ts/openapi.json and packages/sdk-py/openapi.json updated

make generate-sdk-ts
# Expected: packages/sdk-ts/src/ regenerated from the spec
```

### SDK generation (Python)

```bash
# Requires openapi-python-client to be installed
pip install openapi-python-client

make generate-sdk-py
# Expected: packages/sdk-py/src/ populated with a Python client
```

### Docker build (core)

```bash
make build-core
# Expected: successfully tagged mailagent
# Build context is services/core/, Dockerfile is docker/Dockerfile.core
```

### Docker build (UI)

```bash
make build-ui
# Expected: successfully tagged mailagent-web
# Build context is repo root, Dockerfile is docker/Dockerfile.ui
```

### Full stack via Docker Compose

```bash
docker compose up
# Expected:
# - mailserver on ports 25/143/465/587/993
# - mailagent-api on port 8000 (routed via nginx as /api)
# - mailagent-web on port 3000 (routed via nginx as /)
# - nginx on port 80/443

curl http://localhost:8000/health
# Expected: {"status": "ok"}
```

---

## Architectural Invariants Enforced

| Rule | How it's enforced |
|---|---|
| Core logic has no API dependency | `mailagent.core.*` imports only `config`, `providers`, stdlib, and third-party libs. Never `api.*`. |
| API routes contain no business logic | `api/routes/*.py` import only from `config`, `core.*`, and `api/models.py`. |
| Web app communicates via SDK only | `api-client.ts` imports exclusively from `@mailagent/sdk`. No raw `fetch` calls in components. |
| SDK is generated, never hand-written | `packages/sdk-ts/src/` is produced by `openapi-ts`. Files are committed but regenerated via `make generate`. |
| OpenAPI spec is the contract | `packages/sdk-ts/openapi.json` and `packages/sdk-py/openapi.json` are the single source of truth. Generated from the live FastAPI app. |

---

## Future Work

- **Publish `@mailagent/sdk` to npm** — remove `"private": true` from `packages/sdk-ts/package.json`, add a publish workflow.
- **Publish `mailagent-sdk` to PyPI** — add a publish job in CI after `make generate-sdk-py`.
- **Add a second SDK consumer** — any future TypeScript app adds `"@mailagent/sdk": "workspace:*"` and uses the same generated client.
- **Pin SDK version to API version** — once publishing is set up, enforce that `packages/sdk-ts` version matches `services/core` version on each release.
- **Import linter** — add `import-linter` to `services/core/pyproject.toml` to statically verify that `mailagent.core` never imports `mailagent.api`.
