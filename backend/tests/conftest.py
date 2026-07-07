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
