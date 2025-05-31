#!/usr/bin/env python3
"""
Test script for the AI Word Prediction API
"""

import requests
import json
import time

def test_api():
    """Test the API endpoints"""
    base_url = "http://localhost:8000"
    
    print("Testing AI Word Prediction API...")
    
    # Test health check
    try:
        response = requests.get(f"{base_url}/health")
        print(f"Health check: {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {response.json()}")
        else:
            print(f"Health check failed: {response.text}")
            return
    except requests.exceptions.ConnectionError:
        print("❌ Server not running. Please start the server first with: uv run ai-server")
        return
    
    # Test prediction endpoint
    test_cases = [
        {
            "input_phrase": "The capital of France is",
            "top_k_tokens": 5
        },
        {
            "input_phrase": "Once upon a time",
            "top_k_tokens": 3
        },
        {
            "input_phrase": "The weather today is",
            "top_k_tokens": 4
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🧪 Test Case {i}: '{test_case['input_phrase']}'")
        
        try:
            response = requests.post(
                f"{base_url}/predict",
                json=test_case,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Success! Complete sentence: '{result['complete_sentence']}'")
                print("Predictions:")
                for j, pred in enumerate(result['predictions'], 1):
                    print(f"  {j}. {pred['word']:<15} {pred['probability']:.2%} (ID: {pred['token_id']})")
            else:
                print(f"❌ Failed with status {response.status_code}: {response.text}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print("\n🎉 API testing complete!")

if __name__ == "__main__":
    test_api()