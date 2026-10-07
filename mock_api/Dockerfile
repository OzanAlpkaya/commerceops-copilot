# syntax=docker/dockerfile:1
# Build context: the repository root (the uv workspace lock lives there).

FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.11.29 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# Dependencies first, so code changes reuse this layer. uv needs every workspace
# member's pyproject to read the lock, even though only mock-api is installed.
COPY pyproject.toml uv.lock ./
COPY mock_api/pyproject.toml mock_api/README.md mock_api/
COPY copilot/pyproject.toml copilot/README.md copilot/
COPY lumora_corpus/pyproject.toml lumora_corpus/README.md lumora_corpus/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package mock-api --no-install-workspace

COPY mock_api/src mock_api/src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package mock-api --no-editable

FROM python:3.12-slim
RUN useradd --system --uid 10001 --no-create-home app
COPY --from=build /app/.venv /app/.venv
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1
USER app
EXPOSE 8001
# One worker: the rate limiter keeps its state in process memory.
CMD ["uvicorn", "--factory", "mock_api.main:create_app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
