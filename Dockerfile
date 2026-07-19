# syntax=docker/dockerfile:1
# Stage 1 — build the React SPA.
# node:24 = active LTS (v24 LTS since 2025-10; v26 goes LTS 2026-10).
FROM node:24-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2 — FastAPI serves /api/* and the built SPA from one image (one pod
# per env; the frontend/backend split in the repo keeps a two-image evolution
# open).
FROM python:3.12-slim
# VERSION is the single source of truth for the running app version: CI passes
# --build-arg VERSION=main-<shortsha> (staging) or X.Y.Z (releases); the app
# reads APP_VERSION at /api/version. Defaults to "dev" for local builds.
ARG VERSION=dev
ENV APP_VERSION=${VERSION} \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend /frontend/dist ./static
RUN chmod +x /app/entrypoint.sh
USER nobody
EXPOSE 8080
ENTRYPOINT ["/app/entrypoint.sh"]
