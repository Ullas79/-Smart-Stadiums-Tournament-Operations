# managing-python-dependencies

Ensures proper Python dependency management, avoiding global `pip install` and adhering to project-specific tooling.

Use this skill if any of the following are true:
1. Attempting to run `pip install {package_name}`.
2. Python packages or dependencies need to be added or modified.
3. Initiating a new Python project.
4. Creating a new notebook, even if just using BigQuery cells.
5. Generating Python code that includes `import` statements for third-party libraries.
6. Before executing Python scripts via the terminal to ensure the correct virtual environment is active.

## Python Dependency Management Rule

> **BEFORE any `pip install`**: You MUST first detect the project's existing dependency manager and use it correctly. Do NOT override the project's established tooling.
