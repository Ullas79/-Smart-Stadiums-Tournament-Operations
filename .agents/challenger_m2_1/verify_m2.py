import sys
import os
import re
import json

# Add backend directory to sys.path
sys.path.append(r"C:\Users\hp\-Smart-Stadiums-Tournament-Operations\backend")

# Set dummy env vars so settings can load
os.environ["GOOGLE_API_KEY"] = "fake-key-for-testing"

from fastapi.testclient import TestClient
from app.main import create_app

def verify_polling_interval():
    print("=== Checking Polling Interval ===")
    app_path = r"C:\Users\hp\-Smart-Stadiums-Tournament-Operations\frontend\src\App.tsx"
    if not os.path.exists(app_path):
        print(f"Error: {app_path} not found")
        return False
    
    with open(app_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Search for setInterval(..., <number>)
    match = re.search(r"setInterval\(\s*\w+\s*,\s*(\d+)\s*\)", content)
    if not match:
        print("Error: Could not find setInterval call in App.tsx")
        return False
    
    interval = int(match.group(1))
    print(f"Found polling interval: {interval}ms")
    if interval <= 2000:
        print(f"Success: Polling interval is {interval}ms (<= 2000ms)")
        return True
    else:
        print(f"Failure: Polling interval is {interval}ms (> 2000ms)")
        return False

def verify_simulator_behavior():
    print("=== Checking Simulator and API Endpoints ===")
    app = create_app()
    
    with TestClient(app) as client:
        # 1. Health check
        res = client.get("/health")
        assert res.status_code == 200, "Health check failed"
        print("Health check: PASS")
        
        # 2. Initial state
        res = client.get("/state")
        assert res.status_code == 200, "Get state failed"
        state = res.json()
        assert state["venue_name"] == "MetLife Stadium"
        print("Initial state retrieval: PASS")
        
        # Verify that the simulator starts at pre_open with no active incidents
        assert state["match"]["phase"] == "pre_open", f"Expected pre_open phase, got {state['match']['phase']}"
        assert len(state["incidents"]) == 0, f"Expected 0 active incidents, got {len(state['incidents'])}"
        print("Initial phase is pre_open, 0 incidents: PASS")
        
        # 3. Gate Malfunction
        print("\nTriggering Gate Malfunction scenario...")
        res = client.post("/simulator/scenario", json={"scenario": "gate_malfunction"})
        assert res.status_code == 200, "Trigger gate malfunction failed"
        data = res.json()
        assert data["status"] == "success", f"Trigger failed status: {data['status']}"
        incident = data["incident"]
        assert incident is not None, "No incident returned"
        assert incident["type"] == "entry_bottleneck", f"Expected type 'entry_bottleneck', got {incident['type']}"
        assert incident["location"] == "Gate 2 (South Gate)", f"Expected location 'Gate 2 (South Gate)', got {incident['location']}"
        assert incident["severity"] == "high", f"Expected severity 'high', got {incident['severity']}"
        
        # Get state and check G-S and active incidents
        res = client.get("/state")
        state = res.json()
        assert len(state["incidents"]) == 1, f"Expected 1 active incident, got {len(state['incidents'])}"
        assert state["incidents"][0]["incident_id"] == incident["incident_id"], "Incident ID mismatch"
        
        # Check gate G-S
        gate_s = next((g for g in state["gates"] if g["gate_id"] == "G-S"), None)
        assert gate_s is not None, "Gate G-S not found"
        assert gate_s["status"] == "restricted", f"Expected G-S status 'restricted', got {gate_s['status']}"
        assert gate_s["queue_minutes"] == 45.0, f"Expected G-S queue_minutes 45.0, got {gate_s['queue_minutes']}"
        assert gate_s["throughput_per_min"] == 0, f"Expected G-S throughput 0, got {gate_s['throughput_per_min']}"
        print("Gate Malfunction scenario verification: PASS")
        
        # 4. Medical Emergency
        print("\nTriggering Medical Emergency scenario...")
        res = client.post("/simulator/scenario", json={"scenario": "medical_emergency"})
        assert res.status_code == 200, "Trigger medical emergency failed"
        data = res.json()
        assert data["status"] == "success", f"Trigger failed status: {data['status']}"
        incident = data["incident"]
        assert incident is not None, "No incident returned"
        assert incident["type"] == "medical", f"Expected type 'medical', got {incident['type']}"
        assert incident["location"] == "Section 104 (Lower North)", f"Expected location 'Section 104 (Lower North)', got {incident['location']}"
        assert incident["severity"] == "high", f"Expected severity 'high', got {incident['severity']}"
        
        # Get state and check active incidents
        res = client.get("/state")
        state = res.json()
        assert len(state["incidents"]) == 2, f"Expected 2 active incidents, got {len(state['incidents'])}"
        print("Medical Emergency scenario verification: PASS")
        
        # 5. Concession Surge
        print("\nTriggering Concession Surge scenario...")
        res = client.post("/simulator/scenario", json={"scenario": "concession_surge"})
        assert res.status_code == 200, "Trigger concession surge failed"
        data = res.json()
        assert data["status"] == "success", f"Trigger failed status: {data['status']}"
        incident = data["incident"]
        assert incident is not None, "No incident returned"
        assert incident["type"] == "congestion", f"Expected type 'congestion', got {incident['type']}"
        assert incident["location"] == "Concourse A (Club North)", f"Expected location 'Concourse A (Club North)', got {incident['location']}"
        assert incident["severity"] == "high", f"Expected severity 'high', got {incident['severity']}"
        
        # Get state and check C-N zone
        res = client.get("/state")
        state = res.json()
        assert len(state["incidents"]) == 3, f"Expected 3 active incidents, got {len(state['incidents'])}"
        zone_cn = next((c for c in state["crowd"] if c["zone_id"] == "C-N"), None)
        assert zone_cn is not None, "Zone C-N not found"
        assert zone_cn["density"] == 0.90, f"Expected C-N density 0.90, got {zone_cn['density']}"
        print("Concession Surge scenario verification: PASS")
        
        # 6. Reset
        print("\nTriggering Reset scenario...")
        res = client.post("/simulator/scenario", json={"scenario": "reset"})
        assert res.status_code == 200, "Trigger reset failed"
        data = res.json()
        assert data["status"] == "success", f"Trigger failed status: {data['status']}"
        assert data["incident"] is None, "Expected reset incident to be None"
        
        # Get state and check recovery
        res = client.get("/state")
        state = res.json()
        assert len(state["incidents"]) == 0, f"Expected 0 active incidents after reset, got {len(state['incidents'])}"
        gate_s = next((g for g in state["gates"] if g["gate_id"] == "G-S"), None)
        assert gate_s["status"] == "open", f"Expected G-S status 'open' after reset, got {gate_s['status']}"
        assert gate_s["queue_minutes"] == 0.0, f"Expected G-S queue_minutes 0.0 after reset, got {gate_s['queue_minutes']}"
        zone_cn = next((c for c in state["crowd"] if c["zone_id"] == "C-N"), None)
        assert zone_cn["density"] == 0.0, f"Expected C-N density 0.0 after reset, got {zone_cn['density']}"
        print("Reset scenario verification: PASS")
    
    return True

if __name__ == "__main__":
    p_ok = verify_polling_interval()
    s_ok = verify_simulator_behavior()
    
    if p_ok and s_ok:
        print("\nALL VERIFICATIONS PASSED SUCCESSFULLY!")
        sys.exit(0)
    else:
        print("\nSOME VERIFICATIONS FAILED.")
        sys.exit(1)
