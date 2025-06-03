from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pydantic import BaseModel, Field, validator
from typing import List
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch.nn.functional as F
import warnings
import os
import re
import logging
from datetime import datetime
warnings.filterwarnings('ignore')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address, default_limits=["15/minute"])

app = FastAPI(
    title="AI Word Prediction API",
    description="API for predicting next words using AI language models",
    version="1.0.0"
)
app.state.limiter = limiter

def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    return JSONResponse(
        status_code=429,
        content={"error": "Rate limit exceeded", "detail": str(exc)},
    )
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# Add TrustedHostMiddleware to protect against host header attacks
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Allows all hosts, adjust as needed for production
)

# Add HTTPSRedirectMiddleware to redirect HTTP to HTTPS
# Ensure your server is configured for HTTPS for this to work correctly
app.add_middleware(HTTPSRedirectMiddleware)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

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
model_loading_status = "not_loaded"  # "not_loaded", "loading", "loaded", "error"
model_name = "HuggingFaceTB/SmolLM2-1.7B"  # The model being used

class PredictionRequest(BaseModel):
    input_phrase: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="The input phrase to predict the next word for (max 200 characters)"
    )
    top_k_tokens: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Number of top predictions to return (max 10)"
    )

    @validator('input_phrase')
    def validate_input_phrase(cls, v):
        """Validate and sanitize input phrase"""
        if not v or not v.strip():
            raise ValueError('Input phrase cannot be empty')

        # Remove control characters and excessive whitespace
        sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', v)
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()

        if len(sanitized) == 0:
            raise ValueError('Input phrase cannot be empty after sanitization')

        if len(sanitized) > 200:
            raise ValueError('Input phrase too long (max 200 characters)')

        # Basic content filtering - reject potentially malicious patterns
        malicious_patterns = [
            r'<script[^>]*>',
            r'javascript:',
            r'data:',
            r'vbscript:',
            r'on\w+\s*=',
            r'eval\s*\(',
            r'expression\s*\(',
        ]

        for pattern in malicious_patterns:
            if re.search(pattern, sanitized, re.IGNORECASE):
                raise ValueError('Input contains potentially malicious content')

        # Check for excessive repetition (potential DoS)
        if re.search(r'(.{10,})\1{3,}', sanitized):
            raise ValueError('Input contains excessive repetition')

        return sanitized

    @validator('top_k_tokens')
    def validate_top_k(cls, v):
        """Validate top_k_tokens parameter"""
        if v < 1 or v > 10:
            raise ValueError('top_k_tokens must be between 1 and 10')
        return v

class PredictionResult(BaseModel):
    word: str
    probability: float
    token_id: int

class PredictionResponse(BaseModel):
    predictions: List[PredictionResult]
    input_phrase: str
    complete_sentence: str

# Note: The new middleware function `add_security_headers` has been added above this line,
# right after HTTPSRedirectMiddleware and before mounting static files.
# This is a slightly different placement than "before load_model_and_tokenizer",
# but it's a more logical grouping with other middleware.

def load_model_and_tokenizer():
    """Load the model and tokenizer securely"""
    global model, tokenizer, model_loading_status

    if model is None or tokenizer is None:
        model_loading_status = "loading"
        model_name = "HuggingFaceTB/SmolLM2-1.7B"

        try:
            logger.info(f"Loading tokenizer for {model_name}...")

            # Load tokenizer with safety measures
            tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                trust_remote_code=False,  # More secure - don't execute arbitrary code
                use_fast=True,  # Use fast tokenizer when available
                local_files_only=False,  # Allow download but with verification
            )

            # Some models don't have a pad token, so we set it to eos_token
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token

            logger.info("Tokenizer loaded successfully.")

            logger.info(f"Loading model {model_name}...")

            # Load model with safety measures
            model = AutoModelForCausalLM.from_pretrained(
                model_name,
                torch_dtype=torch.float32,  # Use float32 for CPU
                device_map='cpu',
                trust_remote_code=False,  # Critical security fix
                local_files_only=False,
                use_safetensors=True,  # Use safer tensor format when available
                low_cpu_mem_usage=True,  # More efficient memory usage
            )

            # Set model to evaluation mode for inference
            model.eval()

            logger.info("Model loaded successfully!")
            model_loading_status = "loaded"

        except Exception as e:
            logger.error(f"Failed to load model or tokenizer: {str(e)}")
            model_loading_status = "error"
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initialize AI model: {str(e)}"
            )

# Remove startup event to prevent blocking - load model on first request instead
# @app.on_event("startup")
# async def startup_event():
#     """Load model when the server starts"""
#     print(f"Allowed CORS origins: {allowed_origins}")
#     load_model_and_tokenizer()

def ensure_model_loaded():
    """Ensure model is loaded before processing requests"""
    global model, tokenizer, model_loading_status
    if model is None or tokenizer is None:
        load_model_and_tokenizer()

@app.get("/health")
async def health_check():
    """Health check with model status"""
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "tokenizer_loaded": tokenizer is not None,
        "model_loading_status": model_loading_status,
        "model_name": model_name,
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }

@app.get("/api/health")
async def api_health_check():
    """API health check with model status"""
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "tokenizer_loaded": tokenizer is not None,
        "model_loading_status": model_loading_status,
        "model_name": model_name
    }

@app.get("/api")
async def root():
    """API health check endpoint"""
    return {"message": "AI Word Prediction API is running"}

@app.get("/api/model/status")
async def get_model_status():
    """Get the current model loading status"""
    return {
        "status": model_loading_status,
        "model_loaded": model is not None,
        "tokenizer_loaded": tokenizer is not None,
        "model_name": model_name,
        "description": {
            "not_loaded": "Model has not been loaded yet",
            "loading": "Model is currently being loaded",
            "loaded": "Model is ready for predictions",
            "error": "An error occurred while loading the model"
        }.get(model_loading_status, "Unknown status")
    }

@app.post("/api/model/load")
async def load_model():
    """Trigger model loading"""
    global model_loading_status

    if model_loading_status == "loading":
        return {
            "status": "already_loading",
            "message": "Model is already being loaded"
        }

    if model_loading_status == "loaded":
        return {
            "status": "already_loaded",
            "message": "Model is already loaded and ready"
        }

    try:
        load_model_and_tokenizer()
        return {
            "status": "success",
            "message": "Model loaded successfully"
        }
    except HTTPException as e:
        return {
            "status": "error",
            "message": f"Failed to load model: {e.detail}"
        }

@app.get("/")
async def serve_frontend():
    """Serve the frontend application"""
    static_dir = "/app/static"
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    else:
        return {"message": "AI Word Prediction API is running"}

@app.post("/api/predict", response_model=PredictionResponse)
@app.state.limiter.limit("15/minute")
async def predict_next_word(request: Request, payload: PredictionRequest):
    """Predict the next word given an input phrase"""

    # Log the request for monitoring
    logger.info(f"Prediction request: phrase_length={len(payload.input_phrase)}, top_k={payload.top_k_tokens}")

    # Ensure model is loaded
    ensure_model_loaded()

    if model is None or tokenizer is None:
        logger.error("Model or tokenizer not loaded")
        raise HTTPException(status_code=500, detail="Model not loaded")

    try:
        # Additional input validation (Pydantic validators already ran)
        input_phrase = payload.input_phrase.strip()

        # Tokenize the input phrase with safety measures
        try:
            input_ids = tokenizer.encode(
                input_phrase,
                return_tensors="pt",
                max_length=512,  # Limit token length
                truncation=True,  # Truncate if too long
                add_special_tokens=True
            )
        except Exception as e:
            logger.error(f"Tokenization failed: {str(e)}")
            raise HTTPException(status_code=400, detail="Failed to process input text")

        # Check if input is too long after tokenization
        if input_ids.shape[1] > 100:  # Reasonable limit for this application
            raise HTTPException(status_code=400, detail="Input phrase is too long")

        # Get model predictions with timeout protection
        with torch.no_grad():
            try:
                outputs = model(input_ids)
                logits = outputs.logits[0, -1, :]  # Get logits for the last position
            except Exception as e:
                logger.error(f"Model inference failed: {str(e)}")
                raise HTTPException(status_code=500, detail="AI model processing failed")

        # Convert logits to probabilities
        probabilities = F.softmax(logits, dim=-1)

        # Get top-k predictions
        top_k_probs, top_k_indices = torch.topk(probabilities, payload.top_k_tokens)

        # Format results with additional safety checks
        predictions = []
        for i in range(payload.top_k_tokens):
            token_id = top_k_indices[i].item()
            prob = top_k_probs[i].item()

            # Decode the predicted token safely
            try:
                predicted_word = tokenizer.decode([token_id], skip_special_tokens=True)
                predicted_word = predicted_word.strip()

                # Additional safety: filter out control characters from predictions
                predicted_word = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', predicted_word)

                # Filter out empty, whitespace-only, or truly problematic tokens
                if (predicted_word and
                    len(predicted_word) > 0 and
                    len(predicted_word) <= 50 and  # Reasonable word length limit
                    not re.search(r'^[<>{}[\]\\|`~@#$%^&*+=]+$', predicted_word)):  # Block problematic chars only

                    predictions.append(PredictionResult(
                        word=predicted_word,
                        probability=prob,
                        token_id=token_id
                    ))
            except Exception as e:
                logger.warning(f"Failed to decode token {token_id}: {str(e)}")
                continue

        # If no valid predictions after filtering, return error
        if not predictions:
            logger.warning("No valid predictions generated")
            raise HTTPException(status_code=500, detail="No valid word predictions available")

        # Create complete sentence with top prediction
        best_word = predictions[0].word if predictions else ""
        complete_sentence = f"{input_phrase} {best_word}".strip()

        # Log successful prediction
        logger.info(f"Successful prediction: {len(predictions)} results generated")

        return PredictionResponse(
            predictions=predictions,
            input_phrase=input_phrase,
            complete_sentence=complete_sentence
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error in prediction: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error during prediction")

# Catch-all route to serve frontend for client-side routing (must be last)
@app.get("/{full_path:path}")
async def serve_frontend_routes(full_path: str):
    """Serve frontend for all non-API routes (client-side routing)"""
    # Don't interfere with API routes or static assets
    if full_path.startswith("api/") or full_path.startswith("assets/") or full_path.startswith("static/"):
        raise HTTPException(status_code=404, detail="Not found")

    static_dir = "/app/static"
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    else:
        raise HTTPException(status_code=404, detail="Page not found")

def main():
    """Start the FastAPI server"""
    import uvicorn
    uvicorn.run("how_ai_works.api:app", host="127.0.0.1", port=8000, reload=True)

if __name__ == "__main__":
    main()
