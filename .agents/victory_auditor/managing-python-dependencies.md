# Python Dependency Management Rule

**BEFORE any `pip install`**: You MUST first detect the project's existing dependency manager and use it correctly. Do NOT override the project's established tooling.

## Dependency Manager Detection
Before installing ANY Python package, check the workspace for these files **in priority order**:
1. **uv.lock** or **pyproject.toml** with `[tool.uv]` -> **uv**
2. **pyproject.toml** with `[tool.poetry]` -> **Poetry**
3. **Pipfile** -> **Pipenv**
4. **environment.yml** -> **Conda**
5. **requirements.txt** only -> **venv + pip**
6. None -> **venv + pip** (default)
