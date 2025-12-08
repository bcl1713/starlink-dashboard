#!/usr/bin/env python3
import os
import sys
import re
from pathlib import Path

# Configuration
DOCS_DIR = "docs"
EXCLUDED_FILES = {
    "README.md",
    "CONTRIBUTING.md",
    "LICENSE.md",
    "AGENTS.md",
    "CLAUDE.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "CHANGELOG.md"
}

def is_compliant(filename):
    # Check if filename is lowercase and uses hyphens (no underscores, spaces, or uppercase)
    # Allows for .md extension
    
    # Remove extension for checking content
    name_without_ext = os.path.splitext(filename)[0]
    
    # Regex: start of string, one or more lowercase alphanumeric chars, 
    # optionally followed by hyphen and more chars, end of string.
    # Actually, allow numbers too.
    pattern = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')
    
    return bool(pattern.match(name_without_ext))

def main():
    root_dir = Path(os.getcwd())
    docs_path = root_dir / DOCS_DIR
    
    if not docs_path.exists():
        print(f"Error: {DOCS_DIR} directory not found.")
        sys.exit(1)

    print(f"Checking filename conventions in {DOCS_DIR}...")
    
    violations = []
    
    for root, _, files in os.walk(docs_path):
        for file in files:
            if not file.endswith(".md"):
                continue
                
            if file == "README.md":
                continue

            if file in EXCLUDED_FILES:
                continue
            
            relative_path = os.path.relpath(os.path.join(root, file), root_dir)
            
            if not is_compliant(file):
                 violations.append(relative_path)

    if violations:
        print("\nFound the following files violating the 'lowercase-with-hyphens' naming convention:")
        for v in violations:
            print(f"  - {v}")
        print(f"\nTotal violations: {len(violations)}")
        print("\nPlease rename these files to use only lowercase letters, numbers, and hyphens.")
        sys.exit(1)
    else:
        print("All markdown files follow the naming convention.")
        sys.exit(0)

if __name__ == "__main__":
    main()
