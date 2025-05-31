# Deployment Guide for AI Streaming Simulation

This guide covers how to deploy the AI Streaming Simulation application using Docker containers to various cloud platforms.

## 🏗️ Architecture

The application is packaged as a single Docker container that includes:
- **Frontend**: Vue.js application built with Vite
- **Backend**: FastAPI server with AI model (SmolLM2-1.7B)
- **Static File Serving**: FastAPI serves the built frontend assets

## 📋 Prerequisites

- Docker installed on your system
- At least 4GB RAM available for the container
- Internet connection for downloading the AI model

## 🔨 Building the Docker Image

1. **Clone and navigate to the project:**
   ```bash
   cd simple_explainations/how-ai-works
   ```

2. **Build the Docker image:**
   ```bash
   docker build -t ai-streaming-app .
   ```

3. **Test locally:**
   ```bash
   docker run -p 8000:8000 ai-streaming-app
   ```

   Visit `http://localhost:8000` to test the application.

## ☁️ Cloud Deployment Options

### 1. Google Cloud Run

**Advantages:** Serverless, automatic scaling, pay-per-use

```bash
# Build and push to Google Container Registry
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/ai-streaming-app

# Deploy to Cloud Run
gcloud run deploy ai-streaming-app \
  --image gcr.io/YOUR_PROJECT_ID/ai-streaming-app \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 4Gi \
  --cpu 2 \
  --timeout 3600 \
  --set-env-vars="FRONTEND_URL=https://ai-streaming-app-12345.run.app"
```

### 2. AWS App Runner

**Advantages:** Simple deployment, automatic scaling

1. Push image to Amazon ECR:
   ```bash
   aws ecr create-repository --repository-name ai-streaming-app
   docker tag ai-streaming-app:latest YOUR_ACCOUNT.dkr.ecr.REGION.amazonaws.com/ai-streaming-app:latest
   docker push YOUR_ACCOUNT.dkr.ecr.REGION.amazonaws.com/ai-streaming-app:latest
   ```

2. Create App Runner service via AWS Console or CLI

### 3. Azure Container Instances

**Advantages:** Simple container hosting

```bash
# Create resource group
az group create --name ai-streaming-rg --location eastus

# Create container instance
az container create \
  --resource-group ai-streaming-rg \
  --name ai-streaming-app \
  --image ai-streaming-app:latest \
  --cpu 2 \
  --memory 4 \
  --ports 8000 \
  --ip-address Public
```

### 4. Railway

**Advantages:** Git-based deployment, simple setup

1. Connect your GitHub repository to Railway
2. Railway will automatically detect the Dockerfile
3. Set environment variables if needed
4. Deploy with one click

### 5. Render

**Advantages:** Free tier available, automatic deploys

1. Connect your GitHub repository
2. Create a new Web Service
3. Use Docker runtime
4. Set build command: `docker build -t ai-streaming-app .`
5. Set start command: `docker run -p $PORT:$PORT ai-streaming-app`

## 🔧 Environment Configuration

### Required Environment Variables

- `PORT`: Port number (default: 8000)
- `PYTHONPATH`: Python path (set to `/app/src`)

### CORS Configuration Variables

For production deployments, set these environment variables to secure CORS:

- `FRONTEND_URL`: Your main frontend URL (e.g., `https://your-app.com`)
- `ALLOWED_ORIGINS`: Comma-separated list of allowed origins (e.g., `https://your-app.com,https://www.your-app.com`)

**Example for Cloud Run:**
```bash
gcloud run deploy ai-streaming-app \
  --set-env-vars="FRONTEND_URL=https://your-app-12345.run.app,ALLOWED_ORIGINS=https://your-app-12345.run.app"
```

**Example for Railway:**
- Set `FRONTEND_URL` to your Railway app URL
- Set `ALLOWED_ORIGINS` to include your custom domain if you have one

### Optional Configuration

- **Memory**: Minimum 4GB recommended for AI model
- **CPU**: 2+ cores recommended for better performance
- **Timeout**: Set to 300+ seconds for model loading

## 🚀 Performance Optimization

### Model Loading
- The AI model (~3.4GB) is downloaded on first startup
- Consider using a persistent volume for model caching
- Cold start time: 60-120 seconds

### Scaling Considerations
- Each instance loads its own model copy
- Consider using model caching services for multiple instances
- Monitor memory usage (model requires ~3-4GB RAM)

## 🏥 Health Checks

The application provides health check endpoints:
- `GET /health` - Basic health check
- `GET /api/health` - API health with model status

Example health check configuration:
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 30s
  retries: 3
  start_period: 60s
```

## 🔍 Monitoring

### Logs
- Application logs are sent to stdout
- Model loading progress is logged
- API request/response logging available

### Metrics to Monitor
- Memory usage (should be ~4GB)
- CPU usage during inference
- Response times
- Health check status

## 🛠️ Troubleshooting

### Common Issues

1. **Container OOM (Out of Memory)**
   - Increase memory allocation to 4GB+
   - Check if model is loading properly

2. **Slow Cold Starts**
   - Expected on first request (model loading)
   - Consider keeping container warm

3. **Model Loading Failures**
   - Check internet connection for model download
   - Verify sufficient disk space (4GB+)

4. **CORS Issues**
   - Application is configured for flexible CORS
   - Check browser developer tools for errors

### Debug Commands

```bash
# Check container logs
docker logs <container-id>

# Get container stats
docker stats <container-id>

# Access container shell
docker exec -it <container-id> /bin/bash
```

## 📱 Frontend Configuration

The frontend automatically adapts to the deployment environment:
- **Development**: Uses `http://localhost:8000/api`
- **Production**: Uses relative URLs `/api`

No additional frontend configuration required for deployment.

## 🔐 Security Considerations

- The application runs as a single-user container
- No sensitive data is stored in the container
- API endpoints are public (consider adding authentication for production)
- **CORS is properly configured**: Set `FRONTEND_URL` and `ALLOWED_ORIGINS` environmentpermissively (restrict for production)

## 💰 Cost Estimation

### Typical Monthly Costs (US regions):
- **Google Cloud Run**: $10-30 (pay per use)
- **AWS App Runner**: $15-40 (minimum charge applies)
- **Azure Container Instances**: $20-50 (always-on pricing)
- **Railway**: $5-20 (usage-based)
- **Render**: Free tier available, $7+ for paid plans

## 📞 Support

For deployment issues:
1. Check the health endpoints
2. Review container logs
3. Verify resource allocation (4GB+ RAM)
4. Ensure network connectivity for model downloads

The application should be accessible at your deployed URL within 2-3 minutes of container startup.