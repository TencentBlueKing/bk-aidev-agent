#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Post-generation hook for cookiecutter template.
Updates pyproject.toml to use the actual project name.
"""

import os
import re


def update_pyproject_toml():
    """Update pyproject.toml to replace 'ai-plugin' with actual project name."""
    # Get the project name from the current directory (which is the generated project directory)
    project_dir = os.getcwd()
    project_name = os.path.basename(project_dir)

    pyproject_path = os.path.join(project_dir, "pyproject.toml")

    if not os.path.exists(pyproject_path):
        print(f"Warning: {pyproject_path} not found, skipping update.")
        return

    # Read the file
    with open(pyproject_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Replace name = "ai-plugin" with name = "<project_name>"
    # Match: name = "ai-plugin" (with optional whitespace variations)
    pattern = r'name\s*=\s*"ai-plugin"'
    replacement = f'name = "{project_name}"'

    if re.search(pattern, content):
        content = re.sub(pattern, replacement, content)

        # Write back
        with open(pyproject_path, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"Updated pyproject.toml: name changed from 'ai-plugin' to '{project_name}'")
    else:
        print("Warning: Could not find 'name = \"ai-plugin\"' in pyproject.toml")


if __name__ == "__main__":
    update_pyproject_toml()
