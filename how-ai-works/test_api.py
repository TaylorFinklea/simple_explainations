import pytest
import httpx
import asyncio
from fastapi.testclient import TestClient # Only for type hinting if needed, httpx is used

# Assuming your FastAPI app instance is in how_ai_works.api
# Make sure this import works in your test environment
from how_ai_works.api import app, limiter  # Import app and limiter

# Use a base URL that the AsyncClient will hit
# For AsyncClient, this is usually handled by passing the app instance.
BASE_URL = "http://127.0.0.1:8000" # For reference, but not directly used by client with app

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def async_client():
    """Fixture to create an httpx.AsyncClient for testing the FastAPI app."""
    async with httpx.AsyncClient(app=app, base_url=BASE_URL) as client:
        # Ensure the model is loaded before tests run, especially for predict endpoint
        # This helps in making tests for /api/predict more reliable
        print("Attempting to load model before tests...")
        response = await client.post("/api/model/load")
        if response.status_code == 200:
            print("Model loaded successfully for tests.")
        elif response.json().get("status") == "already_loaded" or response.json().get("message") == "Model is already loaded and ready":
            print("Model was already loaded.")
        else:
            print(f"Failed to load model for tests or already loading: {response.status_code} - {response.text}")
            # Depending on strictness, you might want to raise an error here
            # For now, we'll proceed, assuming predict tests will handle model errors if it's critical
        yield client


@pytest.mark.asyncio
async def test_health_check(async_client: httpx.AsyncClient):
    """Test the /health endpoint."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    json_response = response.json()
    assert json_response["status"] == "healthy"
    assert "model_loading_status" in json_response
    print(f"Health check response: {json_response}")

@pytest.mark.asyncio
async def test_api_health_check(async_client: httpx.AsyncClient):
    """Test the /api/health endpoint."""
    response = await async_client.get("/api/health")
    assert response.status_code == 200
    json_response = response.json()
    assert json_response["status"] == "healthy"
    assert "model_loading_status" in json_response
    print(f"API Health check response: {json_response}")


@pytest.mark.asyncio
async def test_successful_prediction(async_client: httpx.AsyncClient):
    """Test a successful prediction from the /api/predict endpoint."""
    payload = {"input_phrase": "The capital of France is", "top_k_tokens": 3}
    # Reset limiter for this specific test to ensure it passes independently
    # This assumes limiter has a 'reset' method or similar, which MemoryStorage does.
    # For SlowAPI, the storage (e.g., MemoryStorage) needs to be accessed.
    # If 'limiter' is the Limiter instance from api.py:
    if hasattr(app.state.limiter._storage, "reset"):
         # This depends on the storage backend. MemoryStorage has clear().
         # If it's a global reset, it might affect other concurrent tests if any.
         # For MemoryStorage, this clears all keys.
        await app.state.limiter._storage.reset()
        print("Limiter reset for test_successful_prediction")


    response = await async_client.post("/api/predict", json=payload)
    
    if response.status_code == 500 and "Model not loaded" in response.text:
        print("Model was not loaded for test_successful_prediction. Attempting to load now.")
        # Try to load model if the fixture didn't catch it or if it unloaded.
        await async_client.post("/api/model/load")
        response = await async_client.post("/api/predict", json=payload) # Retry prediction

    assert response.status_code == 200
    json_response = response.json()
    assert "predictions" in json_response
    assert len(json_response["predictions"]) > 0
    assert json_response["input_phrase"] == payload["input_phrase"]
    assert "complete_sentence" in json_response
    print(f"Successful prediction response: {json_response}")


@pytest.mark.asyncio
async def test_predict_rate_limit_within_limit(async_client: httpx.AsyncClient):
    """Test that requests within the rate limit are successful."""
    # Ensure the limiter is reset for the current test client's IP ("127.0.0.1").
    # Accessing limiter._storage.reset() clears all keys for MemoryStorage.
    if hasattr(app.state.limiter._storage, "reset"):
        await app.state.limiter._storage.reset()
        print("Global limiter storage reset for rate limit tests (within limit).")

    print("Testing rate limit: within limit...")
    for i in range(5):  # Default limit is 5/minute
        response = await async_client.post("/api/predict", json={"input_phrase": f"test within limit {i}", "top_k_tokens": 1})
        if response.status_code != 200:
            # Model loading issues should ideally be caught by the fixture or previous load calls
            assert False, f"Request {i+1} failed unexpectedly: {response.status_code} - {response.text}"
        
        assert response.status_code == 200, f"Request {i+1} failed: {response.text}"
        print(f"Request {i+1} (within limit): Status {response.status_code}")


@pytest.mark.asyncio
async def test_predict_rate_limit_exceeded(async_client: httpx.AsyncClient):
    """Test that requests exceeding the rate limit are rejected."""
    # Ensure the limiter is in a known state (reset, then fill).
    if hasattr(app.state.limiter._storage, "reset"):
        await app.state.limiter._storage.reset()
        print("Global limiter storage reset for rate limit exceeded test.")

    print("Testing rate limit: exceeding limit...")
    # Hit the limit for "127.0.0.1" (the client IP for tests)
    for i in range(5):
        response = await async_client.post("/api/predict", json={"input_phrase": f"test fill limit {i}", "top_k_tokens": 1})
        if response.status_code != 200:
            assert False, f"Model not available or other error during limit filling (request {i+1}): {response.text}"
        assert response.status_code == 200, f"Request {i+1} to fill limit failed: {response.text}"
        print(f"Fill request {i+1}: Status {response.status_code}")

    # The 6th request should be rate-limited
    print("Making the 6th request, expecting 429...")
    response = await async_client.post("/api/predict", json={"input_phrase": "test limit exceeded", "top_k_tokens": 1})
    assert response.status_code == 429
    json_response = response.json()
    assert "error" in json_response
    assert json_response["error"] == "Rate limit exceeded"
    print(f"6th Request (exceeded): Status {response.status_code}, Response: {json_response}")

    # Optional: Test that after the window, requests are allowed again.
    # This requires knowing the exact window duration. Our default is "X/minute".
    # Consider the actual time taken by the 5 calls. If they are very fast,
    # sleeping for nearly the full minute is required.
    # print("Waiting for rate limit window to pass (e.g., 60 seconds)...")
    # await asyncio.sleep(60)
    # response_after_wait = await async_client.post("/api/predict", json={"input_phrase": "test after wait", "top_k_tokens": 1})
    # assert response_after_wait.status_code == 200
    # print(f"Request after waiting: Status {response_after_wait.status_code}")

# To run these tests:
# 1. Ensure `pytest` and `httpx` are installed in your environment.
# 2. Navigate to the `how-ai-works` directory in your terminal.
# 3. Set PYTHONPATH if necessary: `export PYTHONPATH=.` (from the parent of `how_ai_works` directory, e.g. `how-ai-works/..`)
#    Or, more likely, from the root of the `how-ai-works` repo if `how_ai_works` is a package: `export PYTHONPATH=.`
#    If your project is structured as `how-ai-works/src/how_ai_works`, then from `how-ai-works`: `export PYTHONPATH=./src`
#    The key is that `from how_ai_works.api import app` must be resolvable.
#    If `how-ai-works` is the root of the repo containing `pyproject.toml` and a `src` dir, then `PYTHONPATH=.` from `how-ai-works` should work if tests are also in `how-ai-works`.
#    If tests are outside `src`, then `PYTHONPATH=src` might be needed.
#    *Correction based on typical project structure*: If `pyproject.toml` is in `how-ai-works`, and code is in `how-ai-works/src/how_ai_works`,
#    and tests in `how-ai-works/tests`, then `PYTHONPATH=src` from `how-ai-works` is common.
#    However, the problem description implies `how-ai-works/test_api.py` and `how-ai-works/src/how_ai_works/api.py`.
#    So, from the `how-ai-works` directory, `export PYTHONPATH=./src:.` might be robust. Or simply `PYTHONPATH=.` if `how_ai_works` is directly importable.
#    Let's assume the structure `how-ai-works` (root) -> `test_api.py` and `src/how_ai_works/api.py`.
#    So `PYTHONPATH=src` from `how-ai-works` root.
# 4. Run pytest: `pytest` or `python -m pytest` or `pytest test_api.py`

# Notes on `app.state.limiter._storage.reset()`:
# - This method is specific to `slowapi.extension.MemoryStorage`.
# - If a different storage backend (like Redis) were used, clearing would be different
#   (e.g., deleting specific keys from Redis corresponding to "127.0.0.1").
# - Using a global reset is acceptable for these sequential tests, but for parallel tests,
#   it would cause interference. Test-specific rate limit keys or instances would be better there.
# - The `async_client` uses "127.0.0.1" as the remote address, so all calls from it share a rate limit counter.
# - The `async_client` fixture attempts to load the model via `/api/model/load`.
#   If this initial loading fails or is skipped, the predict tests might encounter 500 errors
#   related to "Model not loaded", which the tests try to account for but ideally shouldn't happen
#   if the fixture works as intended.
# - The print statements are for verbosity to help debug during test runs.
# - The `event_loop` fixture is good practice for `pytest-asyncio`.
# - The test for successful prediction also resets the limiter to avoid interference from previous
#   rate limit tests if run out of order or if state persists unexpectedly.
# - `test_predict_rate_limit_within_limit` also resets to ensure it tests its specific scenario cleanly.
# - `test_predict_rate_limit_exceeded` also resets and then fills the limit to ensure it accurately tests the "exceeded" state.
#
# Final check on imports for `how_ai_works.api`:
# The tests need `from how_ai_works.api import app, limiter`.
# This requires `how_ai_works` to be a package that can be found.
# If `api.py` is inside `src/how_ai_works/`, then the `PYTHONPATH` must include `src`.
# If `api.py` is directly under `how_ai_works/` (e.g. `how_ai_works/api.py`), then `PYTHONPATH` must include the parent of `how_ai_works`.
# Given the path `how-ai-works/src/how_ai_works/api.py`, the `src` directory should be in `PYTHONPATH`.
# And the tests are being placed in `how-ai-works/test_api.py`.
# So, running `pytest` from the `how-ai-works` directory with `PYTHONPATH=src` seems correct.
# An alternative is to make `how_ai_works` an installable package (e.g. `pip install -e .`)
# if `pyproject.toml` is set up appropriately.
# The `from how_ai_works.api import app, limiter` assumes `src` is on the path and `how_ai_works` is the package name.
# If the directory structure is `how-ai-works/how_ai_works/api.py`, then `PYTHONPATH=.` from the root is fine.
# The problem states `how-ai-works/src/how_ai_works/api.py`, so `PYTHONPATH=src` is the way.
# The `import from how_ai_works.api` implies that `src` is indeed the root for the package `how_ai_works`.
# So, `from how_ai_works.api ...` is correct if `PYTHONPATH` includes the `src` directory.
# The file `how-ai-works/test_api.py` is outside `src`.
# This seems like a standard layout.
