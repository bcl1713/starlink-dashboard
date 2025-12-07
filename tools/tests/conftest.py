import os
import sys
from pathlib import Path
import pytest

# Add the tools directory to the python path so we can import the scripts
TOOLS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(TOOLS_DIR))

@pytest.fixture
def tools_path():
    return TOOLS_DIR
