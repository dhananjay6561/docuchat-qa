FROM python:3.11-slim

# uv installs exactly what uv.lock pins, so the image matches local and CI environments.
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv

WORKDIR /srv
ENV UV_PROJECT_ENVIRONMENT=/srv/.venv \
    PATH="/srv/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    DB_PATH=/srv/var/docuchat.db

# Dependencies first so code changes don't invalidate the cached dependency layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-cache

COPY app ./app
COPY data ./data

# Run as a non-root user; only the var/ directory (SQLite DB) needs to be writable.
RUN useradd --create-home appuser && mkdir -p /srv/var && chown appuser /srv/var
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
