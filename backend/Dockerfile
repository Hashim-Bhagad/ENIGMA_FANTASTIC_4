FROM ghcr.io/astral-sh/uv:0.12.5 AS uv
FROM python:3.12-slim

COPY --from=uv /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
COPY data ./data
COPY README.md ./
RUN uv sync --locked --no-dev && useradd --uid 10001 --create-home appuser && chown -R appuser:appuser /app
USER appuser
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=4)"]
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
