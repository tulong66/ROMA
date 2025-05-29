"""
Sentient Research Agent Visualization Server

REFACTORED VERSION - Now uses modular architecture!

This is a simplified entry point that delegates to the new modular server implementation.
The old monolithic structure has been broken down into focused, testable modules.

For the new modular structure, see:
- src/sentientresearchagent/server/ - Main server package
- src/sentientresearchagent/server/main.py - Main server class
"""

import sys
import os

# Handle both direct execution and package imports
try:
    # Try relative import (when run as part of package)
    from .server import create_server
except ImportError:
    # Fall back to absolute import (when run directly)
    # Add the parent directory to path so we can import sentientresearchagent
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    
    from sentientresearchagent.server import create_server

# Create and run the server using the new modular architecture
if __name__ == '__main__':
    server = create_server()
    server.run()