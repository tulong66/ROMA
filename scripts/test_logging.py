#!/usr/bin/env python3
"""
Test script to demonstrate the enhanced logging system.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.sentientresearchagent.config.config import LoggingConfig
from src.sentientresearchagent.core.logging_config import (
    setup_logging, log_start, log_success, log_plan, log_execute,
    log_node, log_agent, log_hitl, log_websocket
)
from loguru import logger


def main():
    """Demonstrate various logging features."""
    
    # Configure logging
    config = LoggingConfig(
        level="DEBUG",
        enable_console=True,
        enable_file=False,
        module_levels={
            "sentientresearchagent.server": "INFO",
            "sentientresearchagent.core": "DEBUG",
        }
    )
    
    setup_logging(config)
    
    print("\n=== Enhanced Logging Demo ===\n")
    
    # Basic logging
    logger.info("Standard info message")
    logger.debug("Debug information")
    logger.success("Operation completed successfully")
    logger.warning("This is a warning")
    logger.error("This is an error")
    
    print("\n--- Contextual Logging ---\n")
    
    # Contextual logging with emojis
    log_start("Server initialization")
    log_success("Configuration loaded")
    log_plan("Creating execution plan for task")
    log_execute("Running task executor")
    
    print("\n--- Component Logging ---\n")
    
    # Component-specific logging
    log_node("node_123", "Processing subtask")
    log_agent("ResearchAgent", "Searching for information")
    log_hitl("Waiting for user approval")
    log_websocket("connect", "Client connected from 127.0.0.1")
    
    print("\n--- Automatic Emoji Detection ---\n")
    
    # Messages that trigger automatic emojis
    logger.info("Creating new project")
    logger.info("Loading configuration from disk")
    logger.info("Saving results to cache")
    logger.info("Updating task status")
    logger.info("Agent thinking about the problem")
    logger.info("Task completed successfully")
    
    print("\n--- Module-based Filtering ---\n")
    
    # Simulate logs from different modules
    logger.bind(name="sentientresearchagent.server.api").debug("This debug won't show (filtered)")
    logger.bind(name="sentientresearchagent.server.api").info("This info will show")
    logger.bind(name="sentientresearchagent.core.cache").debug("This debug will show")
    
    print("\n--- Progress Tracking ---\n")
    
    # Progress tracking example
    total_steps = 5
    for i in range(1, total_steps + 1):
        logger.info(f"Step {i}/{total_steps}: Processing...")
        if i == total_steps:
            log_success(f"All {total_steps} steps completed!")
    
    print("\n=== End of Demo ===\n")


if __name__ == "__main__":
    main()