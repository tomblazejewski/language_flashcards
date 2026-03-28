FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency manifest and lockfile first for layer caching
COPY pyproject.toml uv.lock ./

# Install production dependencies only (no dev extras), respecting the lockfile
RUN uv sync --no-dev --frozen

# Copy application source
COPY backend/ ./

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
