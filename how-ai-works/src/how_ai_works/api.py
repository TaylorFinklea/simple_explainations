from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch.nn.functional as F
import warnings
warnings.filterwarnings('ignore')

app = FastAPI(
    title="AI Word Prediction API",
    description="API for predicting next words using AI language models",
    version="1.0.0"
)

# Add CORS middleware to allow frontend connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    load_model_and_tokenizer()

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "AI Word Prediction API is running"}

@app.get("/health")
async def health_check():
    """Health check with model status"""
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "tokenizer_loaded": tokenizer is not None
    }

@app.post("/predict", response_model=PredictionResponse)
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
            
            predictions.append(PredictionResult(
                word=predicted_word,
                probability=prob,
                token_id=token_id
            ))
        
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