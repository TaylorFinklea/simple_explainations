# AI Word Prediction Frontend

A Vue 3 + TypeScript + Tailwind CSS interface for the AI word prediction model.

## Features

- Clean, responsive UI built with Tailwind CSS
- TypeScript for type safety
- Real-time word prediction interface
- Visual probability display with progress bars
- Complete sentence preview

## Setup

1. Install dependencies:
```bash
npm install
```

2. Start the development server:
```bash
npm run dev
```

3. Build for production:
```bash
npm run build
```

## Usage

1. **Start the backend server first:**
   ```bash
   cd ../  # Navigate to how-ai-works directory
   uv sync && uv run ai-server  # requires uv
   # or use pip
   # pip install -e . && ai-server
   ```

2. **Start the frontend (in a new terminal):**
   ```bash
   npm run dev
   ```

3. **Use the application:**
   - Check that the connection status shows "Server connected"
   - Enter a phrase in the input field
   - Set the number of predictions you want (1-10)
   - Click "Predict Next Word" or press Enter
   - View the AI's predicted words with their probabilities

**Note:** The first prediction may take longer as the AI model loads into memory.

## Backend Integration

The UI is now connected to the FastAPI backend! Features include:

✅ **Real-time connection status** - Shows if the backend server is running
✅ **Automatic health checks** - Verifies server connectivity  
✅ **Live AI predictions** - Real responses from HuggingFace SmolLM2-1.7B model
✅ **Error handling** - Clear messages for connection issues

### API Integration Details

The frontend calls these backend endpoints:
- `GET /health` - Check server status and model loading
- `POST /predict` - Get AI word predictions

Request format:
```json
{
  "input_phrase": "The capital of France is",
  "top_k_tokens": 5
}
```

Response format:
```json
{
  "predictions": [
    {
      "word": "Paris",
      "probability": 0.415,
      "token_id": 7042
    }
  ],
  "input_phrase": "The capital of France is",
  "complete_sentence": "The capital of France is Paris"
}
```

## Tech Stack

**Frontend:**
- Vue 3 with Composition API
- TypeScript
- Vite
- Tailwind CSS
- PostCSS

**Backend Integration:**
- FastAPI REST API
- Real-time connection monitoring
- HuggingFace Transformers (SmolLM2-1.7B)
- CORS enabled for local development