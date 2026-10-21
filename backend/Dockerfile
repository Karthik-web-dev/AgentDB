# Build context is the repository root (see docker-compose.yml).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --default-timeout=120 --retries 10 -r requirements.txt

COPY backend/app ./app
# app/db/bootstrap.py resolves ../database relative to the filesystem root inside the image.
COPY database /database

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
