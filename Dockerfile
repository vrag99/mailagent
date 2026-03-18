FROM python:3.12-slim

WORKDIR /app

# Install package dependencies and CLI
COPY pyproject.toml README.md schema.json schema.test.json ./
COPY src/ src/
RUN cp schema.json src/mailagent/schema.json && pip install --no-cache-dir .

# Default config path
ENV MAILAGENT_CONFIG=/app/config.yml

# Entrypoint is the CLI
ENTRYPOINT ["mailagent"]

# Default command
CMD ["run"]
