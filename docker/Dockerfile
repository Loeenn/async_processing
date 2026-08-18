# Сборка зависимостей отдельным слоем: в финальный образ не тянем poetry и кеши
FROM python:3.12-slim-bookworm AS builder

WORKDIR /app

ENV POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_NO_INTERACTION=1 \
    PIP_NO_CACHE_DIR=1

RUN pip install poetry

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --only main


FROM python:3.12-slim-bookworm AS runtime

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN useradd --create-home --uid 1000 app

COPY --from=builder /app/.venv /app/.venv
COPY alembic.ini ./
COPY migrations ./migrations
COPY src ./src
COPY cli ./cli

# Приложение работает не под root
USER app

CMD ["uvicorn", "cli.api:app", "--host", "0.0.0.0", "--port", "8000"]
