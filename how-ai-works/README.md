# AI Word Prediction Demo

A full-stack application that demonstrates how AI language models work by providing interactive word prediction and streaming simulation features. Built with FastAPI (Python) backend and Vue.js (TypeScript) frontend.

## Features

### 🎯 Word Prediction
- Interactive word prediction with configurable parameters
- Real-time AI model predictions using HuggingFace SmolLM2-1.7B
- Visual probability distributions
- Click-to-continue functionality for building sentences

### 🌊 AI Streaming Simulation
- Watch AI build sentences word by word
- Configurable timing, temperature, and prediction parameters
- Real-time streaming with pause/resume controls
- Historical tracking of prediction steps

### 🔄 Model Loading Management
- **New Feature**: Intelligent model loading with user feedback
- Loading status indicators across all pages
- Manual model loading triggers
- Real-time progress monitoring
- Error handling and retry functionality

## Quick Start

### Using Docker (Recommended)

```bash
# Clone and navigate to project
git clone <repository-url>
cd how-ai-works

# Start the application
docker compose up

# Access the application
open http://localhost:8000
```

### Development Setup

```bash
# Backend setup
cd how-ai-works
uv install
uv run ai-server

# Frontend setup (in another terminal)
cd frontend
npm install
npm run dev
```

## Model Loading Experience

### First Time Usage

When you first start the application:

1. **Status Check**: The app automatically checks if the AI model is loaded
2. **Loading UI**: If not loaded, you'll see a "Load AI Model" button
3. **Progress Tracking**: Loading progress is shown with a spinner and status updates
4. **Ready State**: Once loaded, all features become available

### Loading States

- 🟡 **Not Loaded**: Model needs to be initialized
- 🔵 **Loading**: Model is being downloaded/loaded (1-2 minutes)
- 🟢 **Loaded**: Model is ready for predictions
- 🔴 **Error**: Loading failed, retry available

## API Endpoints

### Model Management
- `GET /api/model/status` - Check model loading status
- `POST /api/model/load` - Trigger model loading
- `GET /api/health` - Health check with model status

### Predictions
- `POST /api/predict` - Get word predictions
- `GET /health` - Basic health check

### Example API Usage

```bash
# Check model status
curl http://localhost:8000/api/model/status

# Load model
curl -X POST http://localhost:8000/api/model/load

# Make prediction
curl -X POST http://localhost:8000/api/predict \
  -H "Content-Type: application/json" \
  -d '{"input_phrase": "The wheels on the bus go", "top_k_tokens": 5}'
```

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Vue.js SPA    │────│   FastAPI       │────│   HuggingFace   │
│   (Frontend)    │    │   (Backend)     │    │   SmolLM2-1.7B  │
│                 │    │                 │    │   (AI Model)    │
│ • Model Status  │    │ • Status API    │    │ • Word Predict  │
│ • Loading UI    │    │ • Loading Mgmt  │    │ • Tokenization  │
│ • Predictions   │    │ • CORS Config   │    │ • Probabilities │
│ • Streaming     │    │ • Static Files  │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Testing

### Automated Testing

```bash
# Test all model loading endpoints
python test_model_loading.py

# Demo the user experience flow
python demo_model_loading.py test-flow

# Check current status
python demo_model_loading.py status
```

### Manual Testing

1. **Cold Start**: Restart Docker container to test loading UI
2. **Cross-Page**: Verify status consistency between Word Prediction and Streaming pages
3. **Error Recovery**: Test network failures and recovery
4. **Performance**: Monitor loading times and resource usage

## Configuration

### Environment Variables

```env
PORT=8000                    # Server port
FRONTEND_URL=http://...      # Frontend URL for CORS
ALLOWED_ORIGINS=http://...   # Additional CORS origins
```

### Frontend Configuration

```typescript
// src/config.ts
export const API_CONFIG = {
  baseUrl: '/api',
  healthEndpoint: '/api/health',
  predictEndpoint: '/api/predict',
  modelStatusEndpoint: '/api/model/status',
  modelLoadEndpoint: '/api/model/load',
}
```

## Development

### Project Structure

```
how-ai-works/
├── src/how_ai_works/          # Python backend
│   ├── api.py                 # FastAPI application
│   └── main.py                # Entry point
├── frontend/                  # Vue.js frontend
│   ├── src/
│   │   ├── views/             # Page components
│   │   ├── config.ts          # API configuration
│   │   └── App.vue            # Main app component
│   └── package.json
├── test_model_loading.py      # API tests
├── demo_model_loading.py      # Demo script
├── docker-compose.yml         # Docker configuration
├── Dockerfile                 # Container definition
└── README.md
```

### Key Components

- **Model Loading State**: Global state tracking across frontend and backend
- **Status Polling**: Real-time updates every 2 seconds during loading
- **Error Handling**: Comprehensive error states with retry functionality
- **User Experience**: Consistent loading indicators across all pages

## Performance Notes

- **First Load**: ~1-2 minutes (downloads 1.7B parameter model)
- **Subsequent Loads**: ~10-30 seconds (cached model)
- **Memory Usage**: ~2GB RAM required for model
- **Prediction Speed**: ~100-500ms per prediction

## Troubleshooting

### Model Loading Issues

**Symptoms**: Loading stuck or failed
```bash
# Check logs
docker compose logs ai-streaming-app

# Verify memory
docker stats

# Restart container
docker compose restart
```

**Common Solutions**:
- Ensure 2GB+ RAM available
- Check internet connectivity for model download
- Verify disk space for model caching

### Frontend Issues

**Symptoms**: Status not updating
```bash
# Check browser console for errors
# Verify API endpoints accessible
curl http://localhost:8000/api/model/status

# Check CORS configuration
```

### Performance Issues

**Symptoms**: Slow predictions
- Model may not be fully loaded
- Check CPU/memory usage
- Verify model is in evaluation mode

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Test your changes with `python test_model_loading.py`
4. Submit a pull request

## Support

For issues and questions:
- Check logs: `docker compose logs`
- Run diagnostics: `python demo_model_loading.py status`
- Review troubleshooting section above