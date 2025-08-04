#!/usr/bin/env python3
"""
Demonstrate the clean logging output.
"""

import sys
sys.path.insert(0, '.')

from src.sentientresearchagent.config.config import SentientConfig
from src.sentientresearchagent.core.logging_config import logger, log_start, log_success, log_section

# Load config and setup logging
config = SentientConfig.from_yaml('sentient.yaml')
config.setup_logging()

# Demonstrate clean logging
log_section("SentientResearchAgent Clean Logging Demo")

logger.info("Loading configuration...")
logger.info("Configuration loaded successfully")

log_start("agent initialization")
logger.info("Creating agent registry")
logger.info("Loading agent definitions from YAML")
log_success("All agents initialized")

logger.info("Processing task: Analyze market trends")
logger.debug("This debug message won't show at INFO level")
logger.info("Decomposing task into subtasks")
logger.warning("Rate limit approaching for API calls")
logger.info("Executing subtask 1/3: Gather data")
logger.info("Executing subtask 2/3: Analyze patterns")
logger.info("Executing subtask 3/3: Generate report")

log_success("Task completed successfully!")

logger.error("Example error: Connection timeout")
logger.info("Retrying operation...")
log_success("Operation succeeded on retry")

log_section("Summary")
logger.info("Total tasks processed: 1")
logger.info("Success rate: 100%")
logger.info("Average processing time: 2.3s")

print("\n✨ Clean logging configured successfully!")