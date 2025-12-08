import os
import re
from pathlib import Path
import pytest

# Constants
DOCS_DIR = Path(__file__).parent.parent.parent / "docs"

def get_markdown_files():
    if not DOCS_DIR.exists():
        return []
    return list(DOCS_DIR.rglob("*.md"))

@pytest.mark.parametrize("file_path", get_markdown_files())
def test_markdown_file_not_empty(file_path):
    """Ensure markdown files are not empty."""
    assert file_path.stat().st_size > 0, f"File {file_path} is empty"

@pytest.mark.parametrize("file_path", get_markdown_files())
def test_internal_links(file_path):
    """
    Parse internal links `[text](path)` and verify they exist.
    Ignores external links (http/https).
    Ignores anchors (#section).
    """
    content = file_path.read_text(encoding="utf-8")
    
    # Regex to find standard markdown links: [text](target)
    # This is a basic regex and might need refinement for complex cases
    link_pattern = re.compile(r'\[.*?\]\((.*?)\)')
    
    matches = link_pattern.findall(content)
    
    for target in matches:
        # 1. Skip external links
        if target.startswith(("http://", "https://", "mailto:")):
            continue
            
        # 2. Handle anchors within the same file (e.g. #header)
        if target.startswith("#"):
            continue
            
        # 3. Clean up anchor from target if present (file.md#header)
        url_path = target.split("#")[0]
        if not url_path:
            # Just an anchor like #foo, already skipped above if started with #
            continue

        # 4. Resolve path
        # If it starts with /, it's usually relative to project root in many SSGs, 
        # but in standard markdown viewing it might be absolute path. 
        # We'll assume relative to current file for non-absolute.
        
        if url_path.startswith("/"):
            # Assuming relative to project root for this context, or docs root?
            # Let's assume strict relative paths for now as is common in repos.
            # If a strict absolute path, check from root.
            resolved_path = (DOCS_DIR.parent / url_path.lstrip("/")).resolve()
        else:
            resolved_path = (file_path.parent / url_path).resolve()
            
        # 5. Check existence
        # If it's a directory, maybe it implies index.md? 
        # Let's strictly check file existence first.
        
        if not resolved_path.exists():
            # Failure
            pytest.fail(f"Broken link in {file_path.relative_to(DOCS_DIR.parent)}: '{target}' -> {resolved_path} does not exist.")
