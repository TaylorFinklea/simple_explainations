# AI Word Prediction Demo

Interactive demonstration of how AI language models work, featuring real-time word prediction and streaming simulation. Built with FastAPI (Python) backend and Vue.js (TypeScript) frontend.

## Features

- **Word Prediction**: Interactive AI predictions with HuggingFace SmolLM2-1.7B model
- **Streaming Simulation**: Watch AI build sentences word-by-word with configurable parameters
- **Model Management**: Intelligent loading with status indicators and progress tracking
- **Click-to-Continue**: Build sentences by selecting predicted words

## Quick Start

### Docker (Recommended)

```bash
git clone <repository-url>
cd how-ai-works
docker compose up
open http://localhost:8000
```

### Development

```bash
# Backend
uv install && uv run ai-server

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
```

## First Time Setup

1. Start the application
2. Click "Load AI Model" button (takes 1-2 minutes)
3. Model ready - start making predictions!

**Model States**: 🟡 Not Loaded → 🔵 Loading → 🟢 Ready → 🔴 Error (retry available)

## API Endpoints

| Endpoint | Method | Description |
|----------|---------|-------------|
| `/api/model/status` | GET | Check model loading status |
| `/api/model/load` | POST | Trigger model loading |
| `/api/predict` | POST | Get word predictions |
| `/health` | GET | Health check |

### Example Usage

```bash
# Check status
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
Vue.js Frontend ←→ FastAPI Backend ←→ HuggingFace SmolLM2-1.7B
• Model status UI    • Model management    • Word prediction
• Loading indicators  • CORS & rate limits  • Tokenization
• Streaming display   • Static file serving • Probabilities
```

## Configuration

```env
PORT=8000                    # Server port
FRONTEND_URL=http://...      # CORS configuration
ALLOWED_ORIGINS=http://...   # Additional CORS origins
```

## Performance

- **First Load**: 1-2 minutes (downloads 1.7B parameter model)
- **Memory**: ~2GB RAM required
- **Predictions**: 100-500ms each
- **Rate Limit**: 15 requests/minute

## Troubleshooting

### Model Loading Issues
```bash
# Check logs
docker compose logs ai-streaming-app

# Restart if stuck
docker compose restart

# Clean rebuild (removes cached model)
docker compose down
docker volume rm how-ai-works_huggingface_cache
docker compose build --no-cache && docker compose up
```

**Common fixes:**
- Ensure 2GB+ RAM available
- Check internet connection for model download
- Verify disk space for model caching

### Permission Errors (Docker)
If you see `PermissionError at /home/appuser`:
```bash
docker compose down
docker volume rm how-ai-works_huggingface_cache
docker compose build --no-cache
docker compose up
```

## Testing

```bash
# Test API endpoints
python test_model_loading.py

# Demo user flow
python demo_model_loading.py test-flow

# Check current status
python demo_model_loading.py status
```

## Project Structure

```
how-ai-works/
├── src/how_ai_works/     # Python backend
├── frontend/             # Vue.js frontend
├── scripts/              # Utility scripts
├── test_*.py             # Tests and demos
└── docker-compose.yml    # Docker setup
```

## License

MIT License - see LICENSE file for details.