#!/usr/bin/env python3
"""
Demonstrate the final clean logging output.
"""

import sys
sys.path.insert(0, '.')

# Set up clean logging early
from loguru import logger
logger.remove()

# Add handler with our clean formatter before any other imports
from src.sentientresearchagent.core.logging_config import format_record
logger.add(
    sys.stdout,
    format=format_record,
    colorize=True,
    level="INFO"
)

# Now import everything else
from src.sentientresearchagent.config.config import SentientConfig

# Simulate server startup
logger.info("Starting Sentient Research Agent Server...")
logger.info("Loading configuration from sentient.yaml")

config = SentientConfig.from_yaml('sentient.yaml')
# The setup_logging call will reconfigure with the same clean format
config.setup_logging()

logger.success("Configuration loaded successfully")

logger.info("Initializing system components...")
logger.info("  • System Manager: Ready")
logger.info("  • Agent Registry: Loaded 18 agents")
logger.info("  • Execution Engine: Configured")
logger.info("  • WebSocket Handler: Enabled")

logger.success("All components initialized")

logger.info("Server ready on http://localhost:5000")
logger.info("Frontend available at http://localhost:3000")

logger.info("API Endpoints:")
logger.info("  POST /api/simple/execute - Execute any goal")
logger.info("  POST /api/simple/research - Quick research tasks")
logger.info("  GET  /api/simple/status - Check API status")

logger.info("Example usage:")
logger.info("  curl -X POST http://localhost:5000/api/simple/research \\")
logger.info("       -H 'Content-Type: application/json' \\")
logger.info('       -d \'{"topic": "quantum computing applications"}\'')