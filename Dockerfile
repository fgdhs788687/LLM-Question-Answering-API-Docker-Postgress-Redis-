FROM python:3.12-slim

WORKDIR /app

# Install uv (the same tool you're using locally)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first (Docker caches this layer)
COPY pyproject.toml uv.lock ./

# Install deps into a local .venv inside the image
RUN uv sync --frozen --no-dev

# Copy the rest of the app
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]