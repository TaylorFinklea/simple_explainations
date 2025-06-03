# Deployment Guide

Deploy the AI Word Prediction app to various cloud platforms using Docker.

## Prerequisites

- Docker installed
- 4GB+ RAM available
- Internet connection for model download

## Quick Deploy

### Docker (Local)

```bash
cd how-ai-works
docker compose up
# Visit http://localhost:8000
```

## Cloud Platforms

### Google Cloud Run

```bash
# Build and deploy
gcloud builds submit --tag gcr.io/PROJECT_ID/ai-streaming-app
gcloud run deploy ai-streaming-app \
  --image gcr.io/PROJECT_ID/ai-streaming-app \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 4Gi \
  --cpu 2 \
  --timeout 3600
```

### AWS App Runner

1. Push to ECR:
   ```bash
   aws ecr create-repository --repository-name ai-streaming-app
   docker tag ai-streaming-app:latest ACCOUNT.dkr.ecr.REGION.amazonaws.com/ai-streaming-app:latest
   docker push ACCOUNT.dkr.ecr.REGION.amazonaws.com/ai-streaming-app:latest
   ```
2. Create App Runner service via console

### Railway / Render

1. Connect GitHub repository
2. Auto-detects Dockerfile
3. Deploy with one click
4. Set memory to 4GB+

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `PORT` | Server port | `8000` |
| `FRONTEND_URL` | Main frontend URL | `https://your-app.com` |
| `ALLOWED_ORIGINS` | CORS origins (comma-separated) | `https://your-app.com,https://www.your-app.com` |

### Production CORS Example

```bash
# Cloud Run
gcloud run deploy --set-env-vars="FRONTEND_URL=https://your-app-12345.run.app"

# Docker
docker run -e FRONTEND_URL=https://your-app.com ai-streaming-app
```

## Performance

- **Memory**: 4GB minimum (model needs ~3GB)
- **CPU**: 2+ cores recommended
- **First load**: 60-120 seconds (model download)
- **Cold start**: Expected for serverless platforms

## Health Checks

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 30s
  retries: 3
  start_period: 60s
```

## Troubleshooting

### Model Loading Fails

```bash
# Check logs
docker logs <container-id>

# Permission errors (rebuild)
docker compose down
docker volume rm how-ai-works_huggingface_cache
docker compose build --no-cache
docker compose up
```

### Common Issues

| Problem | Solution |
|---------|----------|
| Out of memory | Increase to 4GB+ RAM |
| Permission errors | Clean rebuild (see above) |
| Slow cold starts | Expected - model loading takes time |
| CORS errors | Set `FRONTEND_URL` and `ALLOWED_ORIGINS` |

### Debug Commands

```bash
# Container stats
docker stats <container-id>

# Shell access
docker exec -it <container-id> /bin/bash

# Cache cleanup
./scripts/cleanup-cache.sh docker
```

## Cost Estimates (Monthly)

| Platform | Cost |
|----------|------|
| Google Cloud Run | $10-30 |
| AWS App Runner | $15-40 |
| Railway | $5-20 |
| Render | Free tier / $7+ |

## Security

- Runs as non-root user in container
- CORS properly configured
- Rate limiting: 15 requests/minute
- No sensitive data stored

## Architecture

```
Docker Container
├── Vue.js Frontend (built)
├── FastAPI Backend
└── HuggingFace Model Cache
```

Single container serves both frontend and API, downloads AI model on first startup.