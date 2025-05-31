# AI Word Prediction API

A FastAPI-based REST API that serves an AI language model for next-word prediction.

## Overview

This API wraps the HuggingFace SmolLM2-1.7B model to provide real-time word prediction capabilities. Given an input phrase, it returns the most likely next words along with their probabilities.

## Quick Start

1. **Install dependencies:**
   ```bash
   uv sync
   ```

2. **Start the server:**
   ```bash
   uv run ai-server
   ```
   
   Or alternatively:
   ```bash
   uv run python -m how_ai_works.api
   ```
   
   Or using uvicorn directly:
   ```bash
   uvicorn how_ai_works.api:app --reload --host 127.0.0.1 --port 8000
   ```

3. **Access the API:**
   - Server: http://localhost:8000
   - Interactive docs: http://localhost:8000/docs
   - Health check: http://localhost:8000/health

## API Endpoints

### `GET /`
Health check endpoint.

**Response:**
```json
{
  "message": "AI Word Prediction API is running"
}
```

### `GET /health`
Detailed health check with model status.

**Response:**
```json
{
  "status": "healthy",
  "model_loaded": true,
  "tokenizer_loaded": true
}
```

### `POST /predict`
Predict the next word(s) for a given input phrase.

**Request Body:**
```json
{
  "input_phrase": "The capital of France is",
  "top_k_tokens": 5
}
```

**Parameters:**
- `input_phrase` (string, required): The input text to predict the next word for
- `top_k_tokens` (integer, optional): Number of top predictions to return (1-20, default: 5)

**Response:**
```json
{
  "predictions": [
    {
      "word": "Paris",
      "probability": 0.85,
      "token_id": 4726
    },
    {
      "word": "the",
      "probability": 0.08,
      "token_id": 279
    }
  ],
  "input_phrase": "The capital of France is",
  "complete_sentence": "The capital of France is Paris"
}
```

## Model Information

- **Model**: HuggingFaceTB/SmolLM2-1.7B
- **Framework**: PyTorch + HuggingFace Transformers
- **Device**: CPU (configured for broad compatibility)
- **Precision**: float32

## Example Usage

### Using curl
```bash
curl -X POST "http://localhost:8000/predict" \
     -H "Content-Type: application/json" \
     -d '{
       "input_phrase": "The weather today is",
       "top_k_tokens": 3
     }'
```

### Using Python requests
```python
import requests

response = requests.post(
    "http://localhost:8000/predict",
    json={
        "input_phrase": "The weather today is",
        "top_k_tokens": 3
    }
)

result = response.json()
print(f"Complete sentence: {result['complete_sentence']}")
for pred in result['predictions']:
    print(f"{pred['word']}: {pred['probability']:.2%}")
```

### Using JavaScript fetch
```javascript
const response = await fetch('http://localhost:8000/predict', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    input_phrase: 'The weather today is',
    top_k_tokens: 3
  })
});

const result = await response.json();
console.log('Predictions:', result.predictions);
```

## Error Handling

The API returns appropriate HTTP status codes:

- `200`: Success
- `400`: Bad Request (empty input phrase, invalid parameters)
- `500`: Internal Server Error (model not loaded, prediction failed)

Example error response:
```json
{
  "detail": "Input phrase cannot be empty"
}
```

## Performance Notes

- **First Request**: May take longer as the model loads on startup
- **Subsequent Requests**: Fast response times as the model stays in memory
- **Memory Usage**: ~3.5GB RAM for the SmolLM2-1.7B model
- **Concurrency**: FastAPI handles multiple requests efficiently

## CORS Configuration

The API is configured to accept requests from:
- `http://localhost:3000` (Vue frontend)
- `http://127.0.0.1:3000`

To add more origins, modify the `allow_origins` list in `api.py`.

## Development

The server runs with auto-reload enabled in development mode. Any changes to the Python files will automatically restart the server.

To run with custom settings:
```bash
uvicorn how_ai_works.api:app --host 0.0.0.0 --port 8000 --reload
```

## Notes on Project Structure

This API follows FastAPI best practices:
- The main application is defined in `api.py`
- A simple `if __name__ == "__main__"` block allows running the file directly
- No separate server startup file needed (this is the recommended FastAPI approach)
- Use uvicorn directly for production deployments
