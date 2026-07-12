import os
import sys
import re
import pytest
from fastapi.testclient import TestClient

# Ensure backend path is in sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.main import create_app
from app.agent.loop import AgentResult

def check_markdown_compliance(text: str) -> list[str]:
    violations = []
    
    # Strip code blocks (```...```) to avoid false positives in code snippets
    clean_text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    # Strip inline code (`...`)
    clean_text = re.sub(r'`.*?`', '', clean_text)
    
    # 1. Check for visual arrows
    arrow_patterns = [
        (r'--->', 'Long hyphen arrow (--->)'),
        (r'===>', 'Long equals arrow (===>)'),
        (r'-->', 'Medium hyphen arrow (-->)'),
        (r'==>', 'Medium equals arrow (==>)'),
        (r'->', 'Short hyphen arrow (->)'),
        (r'=>', 'Short equals arrow (=>)'),
    ]
    for pattern, name in arrow_patterns:
        # Check if the arrow pattern exists outside code blocks
        if re.search(pattern, clean_text):
            # Check context to ensure it's not a regular hyphen or math symbol
            # We look for letters/words on both sides of the arrow
            arrow_context = re.search(rf'\w+\s*{pattern}\s*\w+', clean_text)
            if arrow_context:
                violations.append(f"Contains visual arrow: '{arrow_context.group(0)}' (violates Screen-Reader Guidelines)")
            elif pattern in (r'--->', r'===>', r'-->', r'==>'):
                violations.append(f"Contains visual arrow pattern: '{pattern}'")

    # 2. Check for visual layout flowcharts (e.g. [A] --- [B] or [A] -> [B])
    flowchart_pattern = r'\[.*?\]\s*[-=~]{1,}\s*\[.*?\]'
    if re.search(flowchart_pattern, clean_text):
        violations.append("Contains visual layout flowchart pattern '[A] -- [B]'")

    # 3. Check for unlabeled markdown tables
    # Find markdown table separators (e.g., |---| or |:---:|)
    # Append a dummy empty line at the end to force processing of tables at the end of the text
    lines = [line.strip() for line in clean_text.split('\n')] + [""]
    in_table = False
    table_start_idx = -1
    table_lines = []
    
    for idx, line in enumerate(lines):
        if line.startswith('|') and line.endswith('|') and len(line) > 1:
            if not in_table:
                in_table = True
                table_start_idx = idx
            table_lines.append((idx, line))
        else:
            if in_table:
                # Table ended. Let's process it
                table_end_idx = idx - 1
                # Check for separator row (e.g. |---|)
                has_separator = False
                for t_idx, t_line in table_lines:
                    if re.match(r'^\|[\s\-\:\s|]+\|$', t_line):
                        has_separator = True
                        break
                
                if has_separator:
                    # It's a markdown table. Check for preceding description/summary
                    # We check the 3 lines preceding the table start
                    preceding_text = ""
                    start_lookback = max(0, table_start_idx - 3)
                    for k in range(start_lookback, table_start_idx):
                        preceding_text += " " + lines[k]
                    preceding_text = preceding_text.strip()
                    
                    # We check the 3 lines succeeding the table end
                    succeeding_text = ""
                    end_lookforward = min(len(lines) - 1, table_end_idx + 4) # exclude the dummy line
                    for k in range(table_end_idx + 1, end_lookforward):
                        succeeding_text += " " + lines[k]
                    succeeding_text = succeeding_text.strip()
                    
                    # Has description if either preceding or succeeding text contains descriptive words and is long enough
                    # Minimum 15 characters
                    has_description = (len(preceding_text) > 15) or (len(succeeding_text) > 15)
                    if not has_description:
                        violations.append(f"Contains unlabeled markdown table at lines {table_start_idx+1}-{table_end_idx+1} (missing text summary/description)")
                
                in_table = False
                table_lines = []
                table_start_idx = -1
                
    return violations

# Define Mock Agent for Testing
class MockAgent:
    def __init__(self, reply: str):
        self.reply = reply
    def run(self, message, role, history=None, language="en"):
        return AgentResult(
            reply=self.reply,
            tool_events=[],
            snapshot_summary="Mock snapshot summary"
        )

def run_tests():
    print("==================================================")
    print("RUNNING GENAI AGENT ACCESSIBILITY COMPLIANCE TESTS")
    print("==================================================")
    
    # Create app and client
    app = create_app()
    client = TestClient(app)
    
    # Test cases: (response_text, expected_violations_count, description)
    test_cases = [
        # Case 1: Compliant list
        (
            "To get from Gate 1 to Lower North seats:\n"
            "1. Walk through the main entrance of Gate 1.\n"
            "2. Take the elevator up to the Lower Concourse.\n"
            "3. Walk straight to Section 104.",
            0,
            "Compliant step-by-step route list"
        ),
        # Case 2: Violation with visual arrows
        (
            "Here is the route: Gate 1 ---> Concourse A ---> Section 104",
            1,
            "Visual arrow ---> violation"
        ),
        # Case 3: Violation with equals arrow
        (
            "Here is the route: Gate 1 ===> Concourse A ===> Section 104",
            1,
            "Visual arrow ===> violation"
        ),
        # Case 4: Violation with flowchart pattern
        (
            "Visual diagram:\n[Gate 1] -- [Concourse A] -- [Section 104]",
            1,
            "Visual flowchart diagram violation"
        ),
        # Case 5: Compliant table with description
        (
            "The following table displays the match schedule for the WC2026 Final events. "
            "It lists the local start time and the teams playing in the final matches.\n\n"
            "| Time | Match |\n"
            "| --- | --- |\n"
            "| 20:00 | WC2026 Final |",
            0,
            "Compliant table with preceding description"
        ),
        # Case 6: Violation - Unlabeled table
        (
            "| Time | Match |\n"
            "| --- | --- |\n"
            "| 20:00 | WC2026 Final |",
            1,
            "Unlabeled markdown table violation"
        ),
        # Case 7: Offline default response
        (
            "[OFFLINE MODE] No Gemini API key configured. The assistant is running "
            "without a language model. Set GOOGLE_API_KEY to enable live responses.",
            0,
            "Offline client fallback response (should be compliant)"
        )
    ]
    
    all_passed = True
    for idx, (text, expected_count, desc) in enumerate(test_cases, 1):
        # Override agent in app state
        app.state.agent = MockAgent(text)
        
        # Call chat route
        response = client.post("/chat", json={
            "message": "Hello",
            "role": "fan",
            "language": "en"
        })
        
        assert response.status_code == 200
        reply = response.json()["reply"]
        
        violations = check_markdown_compliance(reply)
        
        print(f"\nTest Case {idx}: {desc}")
        print(f"Response text: {repr(reply)}")
        print(f"Detected violations: {violations}")
        
        if len(violations) == expected_count or (expected_count > 0 and len(violations) > 0):
            print("=> PASSED")
        else:
            print(f"=> FAILED: expected {expected_count} violations, got {len(violations)}")
            all_passed = False
            
    print("\n==================================================")
    if all_passed:
        print("ALL TESTS PASSED SUCCESSFULLY!")
    else:
        print("SOME TESTS FAILED.")
    print("==================================================")
    
    # Also verify prompt.py content
    verify_prompt_instructions()

def verify_prompt_instructions():
    print("\nVerifying instructions in prompt.py...")
    prompt_path = os.path.join(backend_path, "app", "agent", "prompt.py")
    if not os.path.exists(prompt_path):
        print(f"Error: prompt.py not found at {prompt_path}")
        return
        
    with open(prompt_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    required_keywords = [
        "ACCESSIBILITY",
        "screen readers",
        "ASCII art",
        "visual flowchart",
        "unlabeled table",
        "step-by-step",
        "table header"
    ]
    
    missing = []
    for kw in required_keywords:
        if kw.lower() not in content.lower():
            missing.append(kw)
            
    if not missing:
        print("prompt.py contains all required accessibility guardrail instructions!")
        print("Included guidelines:")
        # Print the _ACCESSIBILITY block
        match = re.search(r'_ACCESSIBILITY\s*=\s*"""(.*?)"""', content, re.DOTALL)
        if match:
            print(match.group(1).strip())
    else:
        print(f"Warning: prompt.py is missing keywords related to guardrails: {missing}")

if __name__ == "__main__":
    run_tests()
