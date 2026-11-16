ARG PYTHON_VERSION=3.13
FROM python:${PYTHON_VERSION}-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Needs settings to load, but no real secrets or database.
RUN SECRET_KEY=build-only DATABASE_URL=sqlite:///:memory: REDIS_URL=redis://unused:6379/0 \
    python manage.py collectstatic --noinput

RUN useradd --create-home appuser \
    && mkdir -p /app/media \
    && chown -R appuser /app/media
USER appuser

EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]