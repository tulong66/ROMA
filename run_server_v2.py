#!/usr/bin/env python3
"""
Run the Sentient Research Agent Server with refactored components.

This script starts the server using the new modular architecture.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.sentientresearchagent.server.main_v2 import main

if __name__ == "__main__":
    print("🚀 Starting Sentient Research Agent Server V2 (Refactored Components)")
    print("✨ Using new modular architecture")
    print("-" * 60)
    main()