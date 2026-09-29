FROM node:22-alpine AS live-mirror-build
WORKDIR /src
COPY realtime-web/package.json realtime-web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY realtime-web/ ./
RUN npm run build

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY server/pyproject.toml ./
COPY server/app ./app
COPY scripts/backup_sqlite.py ./scripts/backup_sqlite.py
COPY --from=live-mirror-build /src/dist ./static/live-mirror
RUN python -m pip install --no-cache-dir .

RUN useradd --create-home appuser \
    && mkdir -p /data/media /backups \
    && chown -R appuser:appuser /data /backups
USER appuser

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
