FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first (cached layer)
COPY pyproject.toml uv.lock README.md schema.json schema.test.json ./
COPY src/ src/
RUN cp schema.json src/mailagent/schema.json && uv sync --frozen --no-dev --no-editable

# Default config path
ENV MAILAGENT_CONFIG=/app/config.yml

# Entrypoint is the CLI (use venv binary directly to avoid uv overhead)
ENV PATH="/app/.venv/bin:$PATH"
ENTRYPOINT ["mailagent"]

# Default command
CMD ["run"]
