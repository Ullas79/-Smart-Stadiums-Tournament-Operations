## 2026-07-10T12:05:10Z
Implement the E2E test suite in the file C:\Users\hp\-Smart-Stadiums-Tournament-Operations\backend\tests\test_e2e_suite.py.

The test suite must contain exactly 82 distinct test cases (or more) covering the 4 tiers for features F1 to F7:
- F1: Control Room Dashboard
- F2: Bottleneck Alerts at 85%
- F3: Staff Dispatch Panel
- F4: Multi-Language Concierge
- F5: Wayfinding Indoor Navigation
- F6: Telemetry Simulator
- F7: Scenario Injection Panel

Use `pytest` and `fastapi.testclient.TestClient`. Use a scripted client (like the `ScriptedClient` class from `backend/tests/test_integration.py`) to mock LLM responses where chat behavior is involved. This allows testing the real agent execution loop, role guards, and tool handlers offline and deterministically.

[For full list of tests, refer to the prompt instructions.]
