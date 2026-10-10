FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml alembic.ini ./
COPY alembic ./alembic
COPY src ./src
RUN pip install --no-cache-dir .

FROM base AS runtime
EXPOSE 8000
CMD ["uvicorn", "bike_easyfinder_api.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS test
RUN pip install --no-cache-dir ".[test]"
COPY tests ./tests
CMD ["pytest"]
