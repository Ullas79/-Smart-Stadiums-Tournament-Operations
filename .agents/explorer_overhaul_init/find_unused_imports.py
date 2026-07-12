import os
import ast

BACKEND_DIR = r"C:\Users\hp\-Smart-Stadiums-Tournament-Operations\backend\app"

def get_imported_names(tree):
    # Map from local name to (original name, lineno)
    imports = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                local_name = name.asname or name.name.split('.')[0]
                imports[local_name] = (name.name, node.lineno)
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                # relative import, e.g. from . import foo
                for name in node.names:
                    local_name = name.asname or name.name
                    imports[local_name] = (name.name, node.lineno)
            else:
                for name in node.names:
                    local_name = name.asname or name.name
                    imports[local_name] = (f"{node.module}.{name.name}", node.lineno)
    return imports

def get_used_names(tree):
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Load):
                used.add(node.id)
        # Check attribute accesses (e.g. settings.sim_speed)
        # Actually Name load handles this as long as the base object is a Name (like settings)
    return used

def find_unused_in_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    try:
        tree = ast.parse(content, filename=filepath)
    except SyntaxError:
        return []

    imports = get_imported_names(tree)
    used = get_used_names(tree)
    
    unused = []
    for local_name, (orig_name, lineno) in imports.items():
        if local_name not in used:
            unused.append((local_name, orig_name, lineno))
    return unused

results = {}
for root, _, files in os.walk(BACKEND_DIR):
    for file in files:
        if file.endswith(".py"):
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, BACKEND_DIR)
            unused = find_unused_in_file(full_path)
            if unused:
                results[rel_path] = unused

print("=== UNUSED IMPORTS REPORT ===")
for path, unused in sorted(results.items()):
    print(f"\nFile: app/{path}")
    for local_name, orig_name, lineno in sorted(unused, key=lambda x: x[2]):
        print(f"  [-] Line {lineno}: Unused import `{orig_name}` (as local `{local_name}`)")
