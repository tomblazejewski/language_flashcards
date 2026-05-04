FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_PROJECT_ENVIRONMENT=/opt/venv

# Install dependencies (layer-cached before source copy)
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen --no-install-project

# Copy source and do final sync
COPY backend/ backend/
RUN uv sync --no-dev --frozen

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
