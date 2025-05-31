from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import List
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch.nn.functional as F
import warnings
import os
warnings.filterwarnings('ignore')

app = FastAPI(
    title="AI Word Prediction API",
    description="API for predicting next words using AI language models",
    version="1.0.0"
)

# Add CORS middleware to allow frontend connections
def get_allowed_origins():
    """Get allowed origins based on environment"""
    # Default local development origins
    origins = [
        "http://localhost:3000", 
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ]
    
    # Add production origins from environment variables
    frontend_url = os.getenv("FRONTEND_URL")
    if frontend_url:
        origins.append(frontend_url)
    
    # Add custom origins from environment (comma-separated)
    custom_origins = os.getenv("ALLOWED_ORIGINS")
    if custom_origins:
        origins.extend([origin.strip() for origin in custom_origins.split(",")])
    
    # For Docker environments, allow the container's own URL
    port = os.getenv("PORT", "8000")
    docker_origins = [
        f"http://0.0.0.0:{port}",
        f"http://localhost:{port}",
        f"http://127.0.0.1:{port}"
    ]
    origins.extend(docker_origins)
    
    return list(set(origins))  # Remove duplicates

allowed_origins = get_allowed_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (built frontend)
static_dir = "/app/static"
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    # Mount assets directory for Vite build assets
    assets_dir = "/app/static/assets"
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

# Global variables to store the model and tokenizer
model = None
tokenizer = None

class PredictionRequest(BaseModel):
    input_phrase: str = Field(..., description="The input phrase to predict the next word for")
    top_k_tokens: int = Field(default=5, ge=1, le=20, description="Number of top predictions to return")

class PredictionResult(BaseModel):
    word: str
    probability: float
    token_id: int

class PredictionResponse(BaseModel):
    predictions: List[PredictionResult]
    input_phrase: str
    complete_sentence: str

def load_model_and_tokenizer():
    """Load the model and tokenizer once when the server starts"""
    global model, tokenizer
    
    if model is None or tokenizer is None:
        model_name = "HuggingFaceTB/SmolLM2-1.7B"
        
        print(f"Loading tokenizer for {model_name}...")
        tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        
        # Some models don't have a pad token, so we set it to eos_token
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        
        print("Tokenizer loaded.")
        
        print(f"Loading model {model_name}...")
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float32,  # Use float32 for CPU
            device_map='cpu',
            trust_remote_code=True
        )
        
        print("Model loaded successfully!")

@app.on_event("startup")
async def startup_event():
    """Load model when the server starts"""
    print(f"Allowed CORS origins: {allowed_origins}")
    load_model_and_tokenizer()

@app.get("/health")
async def health_check():
    """Health check with model status"""
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "tokenizer_loaded": tokenizer is not None
    }

@app.get("/api/health")
async def api_health_check():
    """API health check with model status"""
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "tokenizer_loaded": tokenizer is not None
    }

@app.get("/api")
async def root():
    """API health check endpoint"""
    return {"message": "AI Word Prediction API is running"}

@app.get("/")
async def serve_frontend():
    """Serve the frontend application"""
    static_dir = "/app/static"
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    else:
        return {"message": "AI Word Prediction API is running"}

# Catch-all route to serve frontend for client-side routing
@app.get("/{full_path:path}")
async def serve_frontend_routes(full_path: str):
    """Serve frontend for all non-API routes (client-side routing)"""
    # Don't interfere with API routes
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API endpoint not found")
    
    static_dir = "/app/static"
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    else:
        raise HTTPException(status_code=404, detail="Page not found")

@app.post("/api/predict", response_model=PredictionResponse)
async def predict_next_word(request: PredictionRequest):
    """Predict the next word given an input phrase"""
    
    if model is None or tokenizer is None:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    if not request.input_phrase.strip():
        raise HTTPException(status_code=400, detail="Input phrase cannot be empty")
    
    try:
        # Tokenize the input phrase
        input_ids = tokenizer.encode(request.input_phrase, return_tensors="pt")
        
        # Get model predictions
        with torch.no_grad():
            outputs = model(input_ids)
            logits = outputs.logits[0, -1, :]  # Get logits for the last position
        
        # Convert logits to probabilities
        probabilities = F.softmax(logits, dim=-1)
        
        # Get top-k predictions
        top_k_probs, top_k_indices = torch.topk(probabilities, request.top_k_tokens)
        
        # Format results
        predictions = []
        for i in range(request.top_k_tokens):
            token_id = top_k_indices[i].item()
            prob = top_k_probs[i].item()
            
            # Decode the predicted token
            predicted_word = tokenizer.decode([token_id], skip_special_tokens=True)
            predicted_word = predicted_word.strip()
            
            # Filter out empty or whitespace-only tokens
            if predicted_word and len(predicted_word) > 0:
                predictions.append(PredictionResult(
                    word=predicted_word,
                    probability=prob,
                    token_id=token_id
                ))
        
        # If no valid predictions after filtering, return error
        if not predictions:
            raise HTTPException(status_code=500, detail="No valid word predictions available")
        
        # Create complete sentence with top prediction
        best_word = predictions[0].word if predictions else ""
        complete_sentence = f"{request.input_phrase} {best_word}".strip()
        
        return PredictionResponse(
            predictions=predictions,
            input_phrase=request.input_phrase,
            complete_sentence=complete_sentence
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

def main():
    """Start the FastAPI server"""
    import uvicorn
    uvicorn.run("how_ai_works.api:app", host="127.0.0.1", port=8000, reload=True)

if __name__ == "__main__":
    main()