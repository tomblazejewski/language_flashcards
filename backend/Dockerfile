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
# Keep the same layout as the repo (backend/ inside /app) so the package
# path declared in pyproject.toml ("packages = ['backend']") is satisfied.
COPY backend/ backend/
RUN uv sync --no-dev --frozen

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
