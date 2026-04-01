.PHONY: dev dev-core dev-ui generate generate-schema generate-sdk-ts generate-sdk-py build build-core build-ui test lint

# Development
dev-core: ## Start the API server
	cd services/core && uv run mailagent serve --host 0.0.0.0 --port 8000

dev-ui: ## Start the web UI dev server
	cd services/ui && pnpm dev

dev: ## Start all services in parallel
	$(MAKE) dev-core &
	$(MAKE) dev-ui

# SDK generation
generate-schema: ## Extract OpenAPI spec from the Python app
	cd services/core && uv run python3 -c " \
	  from mailagent.api import create_app; \
	  from mailagent.config import Config, ConfigManager, Defaults, Settings; \
	  import json; \
	  cm = ConfigManager(Config(providers={}, defaults=Defaults(classify_provider='', reply_provider=''), inboxes=[], settings=Settings()), '/dev/null'); \
	  spec = create_app(cm).openapi(); \
	  open('../../packages/sdk-ts/openapi.json','w').write(json.dumps(spec, indent=2)); \
	  open('../../packages/sdk-py/openapi.json','w').write(json.dumps(spec, indent=2))"

generate-sdk-ts: generate-schema ## Generate TypeScript SDK
	cd packages/sdk-ts && pnpm generate

generate-sdk-py: generate-schema ## Generate Python SDK
	cd packages/sdk-py && uv run openapi-python-client generate --path openapi.json --output-path src --overwrite

generate: generate-sdk-ts generate-sdk-py ## Regenerate all SDKs

# Build
build-core: ## Build the core Docker image
	docker build -f docker/Dockerfile.core services/core -t mailagent

build-ui: ## Build the web UI Docker image
	docker build -f docker/Dockerfile.ui . -t mailagent-web

build: build-core build-ui ## Build all Docker images

# Test
test: ## Run Python tests
	cd services/core && uv run pytest -q

# Lint
lint: ## Run linters
	cd services/core && uv run ruff check
	cd services/ui && pnpm lint

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
