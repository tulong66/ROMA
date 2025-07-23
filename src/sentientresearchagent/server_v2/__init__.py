"""
Server V2 with refactored components.

This module provides the server implementation using the new modular architecture.
"""

from .main import SentientServerV2, create_server_v2, main

__all__ = [
    "SentientServerV2",
    "create_server_v2",
    "main"
]