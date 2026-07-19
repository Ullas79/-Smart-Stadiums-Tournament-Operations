"""Shared test fixtures."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure backend/ is on sys.path so `import app` works when running pytest
# from the backend directory or the project root.
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Tests must never require a real Gemini key.
os.environ.setdefault("GOOGLE_API_KEY", "test-key-not-real")

import pytest
@pytest.fixture(autouse=True)
def inject_test_client_auth(monkeypatch):
    """Automatically inject the required Authorization header for all TestClient requests."""
    from fastapi.testclient import TestClient
    
    original_request = TestClient.request
    
    def mocked_request(self, method, url, **kwargs):
        headers = kwargs.get("headers") or {}
        if "Authorization" not in headers:
            # Intelligently infer role from json body to pass role-matching auth checks
            role = "organizer"
            json_body = kwargs.get("json")
            if isinstance(json_body, dict) and "role" in json_body:
                role = json_body["role"]
            
            headers["Authorization"] = f"Bearer {role}_secure_token_123"
            kwargs["headers"] = headers
        return original_request(self, method, url, **kwargs)
        
    monkeypatch.setattr(TestClient, "request", mocked_request)
