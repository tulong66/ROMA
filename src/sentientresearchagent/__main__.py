"""
Main entry point for the sentientresearchagent package.

Usage:
    python -m sentientresearchagent
"""

from .server import create_server

if __name__ == '__main__':
    print("🚀 Starting Sentient Research Agent Server...")
    server = create_server()
    server.run() 