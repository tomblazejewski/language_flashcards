FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Place the virtualenv outside the source bind-mount so a docker-compose
# volume mount of ./backend:/app never shadows the installed packages.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

# Copy dependency manifest and lockfile first for layer caching.
# Install third-party dependencies without the project itself so this
# expensive layer is only invalidated when dependencies change.
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen --no-install-project

# Copy application source, then install the project itself.
COPY backend/ ./
RUN uv sync --no-dev --frozen

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
