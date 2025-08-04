#!/usr/bin/env python3
"""
Test truly minimal logging output.
"""

# First set up ultra-minimal logging before any imports
from loguru import logger
import sys

# Remove all handlers
logger.remove()

# Add a super simple handler - just the message, nothing else
logger.add(
    sys.stdout,
    format="{message}",
    colorize=False,
    level="INFO"
)

# Now import and run
sys.path.insert(0, '.')
from src.sentientresearchagent.config.config import SentientConfig

logger.info("Loading configuration...")
config = SentientConfig.from_yaml('sentient.yaml')
logger.info("Configuration loaded!")

logger.info("\nStarting server...")
logger.info("Server ready on http://localhost:5000")
logger.info("\nExample API call:")
logger.info("curl -X POST http://localhost:5000/api/simple/research \\")
logger.info("     -H 'Content-Type: application/json' \\")
logger.info('     -d \'{"topic": "quantum computing"}\'')