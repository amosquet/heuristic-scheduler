import sys
from pathlib import Path

# Add project root to sys.path so root modules (data, manager, simulate, main) can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from main import main

__all__ = ["main"]

