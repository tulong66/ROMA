#!/usr/bin/env python
"""
Test script to verify max_recursion_depth is respected
"""

import asyncio
from sentientresearchagent import SentientAgent
from sentientresearchagent.config import SentientConfig

async def test_max_depth():
    # Create config with max_recursion_depth = 2
    config = SentientConfig()
    config.execution.max_recursion_depth = 2
    config.execution.enable_hitl = False  # Disable HITL for testing
    
    # Create agent
    agent = await SentientAgent.create(config=config)
    
    # Test task that would normally create deep hierarchy
    task = "Create a comprehensive guide for building a modern web application with authentication, database, and deployment"
    
    print(f"Testing with max_recursion_depth = {config.execution.max_recursion_depth}")
    print(f"Task: {task}")
    print("-" * 80)
    
    try:
        result = await agent.process_task(task)
        print("Result:", result)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_max_depth())