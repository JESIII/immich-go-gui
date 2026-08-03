FROM python:3.13-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy workspace code
COPY . /app

# Install python dependencies including web extra (no dev tooling)
RUN uv sync --extra web --no-dev

# Ensure persistent config directory exists
RUN mkdir -p /config

EXPOSE 8080

ENV HOST=0.0.0.0
ENV PORT=8080

CMD ["/bin/sh", "-c", "uv run python web.py --host 0.0.0.0 --port 8080"]
