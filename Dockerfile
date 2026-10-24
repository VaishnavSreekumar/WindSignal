# Multi-stage Dockerfile for WindSignal
# Stage 1: Build Frontend Assets
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Production Python Backend Service
FROM python:3.11-slim AS backend
WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code, data, and docs
COPY src/ ./src/
COPY data/ ./data/
COPY docs/ ./docs/

# Copy built frontend distribution into static serving location if needed
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Expose standard API port
EXPOSE 8000

ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Run FastAPI server
CMD uvicorn src.api:app --host 0.0.0.0 --port ${PORT}
