import os
import ast
import re

BACKEND_DIR = r"C:\Users\hp\-Smart-Stadiums-Tournament-Operations\backend\app"

def check_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    try:
        tree = ast.parse(content, filename=filepath)
    except SyntaxError as e:
        return {"error": f"Syntax error: {e}"}

    issues = {
        "missing_module_docstring": False,
        "functions": [],
        "bare_excepts": [],
        "duplicate_imports": [],
    }

    # Module docstring
    module_doc = ast.get_docstring(tree)
    if not module_doc:
        issues["missing_module_docstring"] = True

    # Check for duplicate imports and bare excepts
    import_lines = []
    # Simple ast traversal
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            # convert import to string representation for comparison
            import_str = ast.unparse(node).strip()
            import_lines.append((import_str, node.lineno))
        
        elif isinstance(node, ast.Try):
            for handler in node.handlers:
                # Bare except: handler.type is None
                if handler.type is None:
                    issues["bare_excepts"].append({
                        "line": handler.lineno,
                        "type": "bare_except"
                    })
                # except Exception:
                elif isinstance(handler.type, ast.Name) and handler.type.id == "Exception":
                    body_str = ""
                    if len(handler.body) == 1:
                        if isinstance(handler.body[0], ast.Pass):
                            body_str = "pass"
                        elif isinstance(handler.body[0], ast.Return):
                            body_str = "return"
                    issues["bare_excepts"].append({
                        "line": handler.lineno,
                        "type": f"except Exception ({body_str if body_str else 'has body'})"
                    })

    # Find duplicate imports
    seen_imports = {}
    for imp_str, lineno in import_lines:
        if imp_str in seen_imports:
            issues["duplicate_imports"].append({
                "line": lineno,
                "statement": imp_str,
                "original_line": seen_imports[imp_str]
            })
        else:
            seen_imports[imp_str] = lineno

    # Check functions and methods
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_name = node.name
            line = node.lineno
            doc = ast.get_docstring(node)
            
            # 1. Missing docstring
            has_docstring = doc is not None and doc.strip() != ""
            
            # 2. Google style check if docstring exists
            google_style = True
            missing_args_section = False
            missing_returns_section = False
            
            # Check if arguments are defined
            args = [a.arg for a in node.args.args if a.arg not in ("self", "cls")]
            if args and has_docstring:
                if not re.search(r"\bArgs:\s*", doc):
                    missing_args_section = True
                    google_style = False
            
            # Check if there is a return annotation (other than None) and return statements
            has_return_annotation = node.returns is not None and not (isinstance(node.returns, ast.Constant) and node.returns.value is None)
            if has_return_annotation and has_docstring:
                if not re.search(r"\bReturns:\s*", doc):
                    missing_returns_section = True
                    google_style = False

            # 3. Check for missing type hints on arguments (excluding self, cls)
            missing_arg_hints = []
            for arg in node.args.args:
                if arg.arg in ("self", "cls"):
                    continue
                if arg.annotation is None:
                    missing_arg_hints.append(arg.arg)
            
            if node.args.vararg and node.args.vararg.annotation is None:
                missing_arg_hints.append(f"*{node.args.vararg.arg}")
            if node.args.kwarg and node.args.kwarg.annotation is None:
                missing_arg_hints.append(f"**{node.args.kwarg.arg}")

            # 4. Check for missing return type hint
            missing_return_hint = node.returns is None

            issues["functions"].append({
                "name": func_name,
                "line": line,
                "has_docstring": has_docstring,
                "google_style": google_style,
                "missing_args_section": missing_args_section,
                "missing_returns_section": missing_returns_section,
                "missing_arg_hints": missing_arg_hints,
                "missing_return_hint": missing_return_hint
            })

    return issues

# Traverse all files
results = {}
for root, _, files in os.walk(BACKEND_DIR):
    for file in files:
        if file.endswith(".py"):
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, BACKEND_DIR)
            results[rel_path] = check_file(full_path)

# Print report in structured way
output_path = r"C:\Users\hp\-Smart-Stadiums-Tournament-Operations\.agents\explorer_overhaul_init\python_audit_utf8.txt"
with open(output_path, "w", encoding="utf-8") as out:
    def write_line(line):
        print(line)
        out.write(line + "\n")

    write_line("=== PYTHON STATIC ANALYSIS REPORT ===")
    for path, issues in sorted(results.items()):
        if "error" in issues:
            write_line(f"File: {path} - ERROR: {issues['error']}")
            continue

        has_issues = (
            issues["missing_module_docstring"] or
            issues["bare_excepts"] or
            issues["duplicate_imports"] or
            any(
                not f["has_docstring"] or
                not f["google_style"] or
                f["missing_arg_hints"] or
                f["missing_return_hint"]
                for f in issues["functions"]
            )
        )

        if not has_issues:
            continue

        write_line(f"\nFile: app/{path}")
        if issues["missing_module_docstring"]:
            write_line("  [-] Missing module-level docstring")
        
        for be in issues["bare_excepts"]:
            write_line(f"  [-] Line {be['line']}: Bare or generic except block ({be['type']})")
            
        for di in issues["duplicate_imports"]:
            write_line(f"  [-] Line {di['line']}: Duplicate import statement: `{di['statement']}` (original on line {di['original_line']})")

        for f in sorted(issues["functions"], key=lambda x: x["line"]):
            func_issues = []
            if not f["has_docstring"]:
                func_issues.append("missing docstring")
            else:
                if f["missing_args_section"]:
                    func_issues.append("docstring missing 'Args:' section")
                if f["missing_returns_section"]:
                    func_issues.append("docstring missing 'Returns:' section")
            
            if f["missing_arg_hints"]:
                func_issues.append(f"missing type hints for args: {', '.join(f['missing_arg_hints'])}")
                
            if f["missing_return_hint"]:
                func_issues.append("missing return type hint")

            if func_issues:
                write_line(f"  [-] Line {f['line']}: Function `{f['name']}()` - {', '.join(func_issues)}")
