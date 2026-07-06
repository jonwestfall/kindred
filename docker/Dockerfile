# syntax=docker/dockerfile:1
FROM node:22-alpine AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    KINDRED_HOST=0.0.0.0 \
    KINDRED_PORT=8000 \
    KINDRED_DATABASE_PATH=/app/data/kindred.db
WORKDIR /app
COPY backend/ ./backend/
RUN pip install --no-cache-dir "./backend[notifications]"
COPY config/ ./config/
COPY data/seed/ ./data/seed/
COPY --from=frontend-build /build/frontend/dist/ ./frontend/dist/
RUN mkdir -p /app/data
EXPOSE 8000
VOLUME ["/app/data"]
HEALTHCHECK --interval=30s --timeout=4s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"
CMD ["uvicorn", "kindred.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]

