import pytest
from fastapi.testclient import TestClient
import asyncio
from httpx import AsyncClient

from app.main import app
from app.models.roles import Role

client = TestClient(app)

@pytest.mark.asyncio
async def test_security_missing_token():
    """Verify that calling an endpoint without a token results in 401."""
    response = client.post("/chat", json={
        "message": "Hello",
        "role": "fan",
        "history": [],
        "language": "en"
    })
    assert response.status_code == 401
    assert "Missing authorization token" in response.json()["detail"]

@pytest.mark.asyncio
async def test_security_invalid_token():
    """Verify that calling an endpoint with an invalid token results in 401/403."""
    response = client.post("/chat", json={
        "message": "Hello",
        "role": "fan",
        "history": [],
        "language": "en"
    }, headers={"Authorization": "Bearer bad_token"})
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_security_role_mismatch():
    """Verify that a 'Fan' token cannot execute an action as an 'Organizer'."""
    # Attempting to chat as an organizer using a fan token
    response = client.post("/chat", json={
        "message": "Close all gates",
        "role": "organizer",
        "history": [],
        "language": "en"
    }, headers={"Authorization": "Bearer fan_secure_token_123"})
    assert response.status_code == 403
    assert "Cannot execute actions as organizer with fan token" in response.json()["detail"]

    # Attempting to trigger a scenario (Organizer only) using a fan token
    response = client.post("/simulator/scenario", json={
        "scenario": "medical_emergency"
    }, headers={"Authorization": "Bearer fan_secure_token_123"})
    assert response.status_code == 403
    assert "Only organizers can trigger scenarios" in response.json()["detail"]

from httpx import AsyncClient, ASGITransport
from app.core.config import settings
import concurrent.futures

def test_simulation_stress_stability():
    """Run 100 concurrent random state-mutating requests against the simulation engine."""
    original_limit = settings.rate_limit_requests
    settings.rate_limit_requests = 10000
    try:
        # Using 'with TestClient' ensures the FastAPI lifespan runs
        # so app.state.simulator is initialized properly.
        with TestClient(app) as client:
            def make_request(i: int):
                if i % 10 == 0:
                    res = client.post("/simulator/scenario", json={
                        "scenario": "medical_emergency"
                    }, headers={"Authorization": "Bearer organizer_secure_token_123"})
                    assert res.status_code == 200
                else:
                    res = client.get("/state")
                    assert res.status_code == 200
                return True

            with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
                futures = [executor.submit(make_request, i) for i in range(100)]
                for f in concurrent.futures.as_completed(futures):
                    try:
                        f.result()
                    except Exception as e:
                        pytest.fail(f"Request failed with exception: {e}")

            # Verify the final state is mathematically consistent
            state_res = client.get("/state")
            assert state_res.status_code == 200
            state = state_res.json()
            
            for zone in state["crowd"]:
                assert 0 <= zone["occupancy"] <= zone["capacity"], f"Zone {zone['zone_id']} occupancy out of bounds"
                assert 0.0 <= zone["density"] <= 1.0, f"Zone {zone['zone_id']} density out of bounds"
    finally:
        settings.rate_limit_requests = original_limit
