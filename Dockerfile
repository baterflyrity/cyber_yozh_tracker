# Development image for the CyberYozh task manager.
# The compose file runs this with SQLite stored in a named volume.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy

# uv gives us reproducible installs straight from uv.lock.
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /uvx /bin/

WORKDIR /app

# Warm the dependency layer first so code changes do not rebuild dependencies.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen

# Application source.
COPY . .

# Make the virtualenv interpreter the default `python` for the entrypoint.
ENV PATH="/app/.venv/bin:$PATH"

RUN chmod +x /app/docker/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
