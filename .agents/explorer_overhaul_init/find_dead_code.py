import os
import ast

BACKEND_DIR = r"C:\Users\hp\-Smart-Stadiums-Tournament-Operations\backend\app"

def find_unreachable_statements(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    try:
        tree = ast.parse(content, filename=filepath)
    except SyntaxError:
        return []

    unreachable = []
    
    # Helper to check lists of statements
    def check_body(body):
        terminator_found = False
        for stmt in body:
            if terminator_found:
                unreachable.append((stmt.lineno, ast.unparse(stmt).strip()))
                continue
            
            # Check if this statement is a terminator
            if isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                terminator_found = True
            
            # Recurse into nested structures
            for child in ast.iter_child_nodes(stmt):
                if isinstance(child, list):
                    check_body(child)
                elif hasattr(child, "body"):
                    if isinstance(child.body, list):
                        check_body(child.body)
                    if hasattr(child, "orelse") and isinstance(child.orelse, list):
                        check_body(child.orelse)
                    if hasattr(child, "finalbody") and isinstance(child.finalbody, list):
                        check_body(child.finalbody)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            check_body(node.body)
        elif isinstance(node, ast.Module):
            check_body(node.body)
            
    return unreachable

results = {}
for root, _, files in os.walk(BACKEND_DIR):
    for file in files:
        if file.endswith(".py"):
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, BACKEND_DIR)
            unreach = find_unreachable_statements(full_path)
            if unreach:
                results[rel_path] = unreach

print("=== UNREACHABLE CODE REPORT ===")
for path, unreach in sorted(results.items()):
    print(f"\nFile: app/{path}")
    for lineno, stmt in unreach:
        print(f"  [-] Line {lineno}: Unreachable statement: `{stmt}`")
