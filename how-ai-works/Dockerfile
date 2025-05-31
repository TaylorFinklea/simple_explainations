# Multi-stage build for AI Streaming Simulation App
FROM node:18-slim as frontend-builder

# Set working directory for frontend build
WORKDIR /app/frontend

# Copy frontend package files
COPY frontend/package*.json ./

# Install frontend dependencies (including dev dependencies for build)
RUN npm ci

# Copy frontend source code
COPY frontend/ ./

# Build frontend for production (skip type checking for Docker build)
RUN npx vite build

# Python backend stage
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast Python package management
RUN pip install uv

# Copy Python project files
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/

# Install Python dependencies directly with pip from pyproject.toml
RUN pip install -e .

# Copy built frontend from previous stage
COPY --from=frontend-builder /app/frontend/dist ./static

# Create a startup script that serves both frontend and API
RUN echo '#!/bin/bash\nexec python -m uvicorn how_ai_works.api:app --host 0.0.0.0 --port $PORT' > start.sh && \
    chmod +x start.sh

# Expose port (default to 8000, but allow override with PORT env var)
EXPOSE 8000

# Set environment variables
ENV PORT=8000
ENV PYTHONPATH=/app/src
# CORS configuration (override these in production)
# ENV FRONTEND_URL=https://your-app.com
# ENV ALLOWED_ORIGINS=https://your-app.com,https://www.your-app.com

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:$PORT/health || exit 1

# Run the application
CMD ["./start.sh"]