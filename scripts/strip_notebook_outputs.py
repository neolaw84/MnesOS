#!/usr/bin/env python3
"""
Strip outputs from Jupyter notebooks.

This script removes all cell outputs from .ipynb files while preserving
the code and markdown content. Useful for keeping notebooks clean in version control.

Usage:
    python scripts/strip_notebook_outputs.py <notebook_file> [notebook_file] ...
"""

import json
import sys
from pathlib import Path


def strip_notebook_outputs(notebook_path):
    """
    Remove all outputs from a Jupyter notebook.
    
    Args:
        notebook_path: Path to the .ipynb file
        
    Returns:
        bool: True if file was modified, False otherwise
    """
    notebook_path = Path(notebook_path)
    
    if not notebook_path.exists():
        print(f"Warning: File not found: {notebook_path}", file=sys.stderr)
        return False
    
    if not notebook_path.suffix == ".ipynb":
        print(f"Warning: Not a notebook file: {notebook_path}", file=sys.stderr)
        return False
    
    # Read the notebook
    with open(notebook_path, "r", encoding="utf-8") as f:
        notebook = json.load(f)
    
    # Track if any changes were made
    modified = False
    
    # Process each cell
    if "cells" in notebook:
        for cell in notebook["cells"]:
            # Remove outputs from code cells
            if cell.get("cell_type") == "code":
                if "outputs" in cell and cell["outputs"]:
                    cell["outputs"] = []
                    modified = True
                # Also clear execution_count
                if "execution_count" in cell:
                    cell["execution_count"] = None
                    modified = True
    
    # Write back if modified
    if modified:
        with open(notebook_path, "w", encoding="utf-8") as f:
            json.dump(notebook, f, indent=1, ensure_ascii=False)
            f.write("\n")  # Ensure file ends with newline
        return True
    
    return False


def main():
    """Process multiple notebook files."""
    if len(sys.argv) < 2:
        print("Usage: strip_notebook_outputs.py <notebook_file> [notebook_file] ...", file=sys.stderr)
        sys.exit(1)
    
    modified_files = []
    error_count = 0
    
    for notebook_path in sys.argv[1:]:
        try:
            if strip_notebook_outputs(notebook_path):
                modified_files.append(notebook_path)
                print(f"Stripped outputs: {notebook_path}")
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in {notebook_path}: {e}", file=sys.stderr)
            error_count += 1
        except Exception as e:
            print(f"Error processing {notebook_path}: {e}", file=sys.stderr)
            error_count += 1
    
    if error_count > 0:
        sys.exit(1)
    
    if modified_files:
        print(f"\nModified {len(modified_files)} notebook(s)")
    
    sys.exit(0)


if __name__ == "__main__":
    main()
