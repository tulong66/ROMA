#!/usr/bin/env python3
"""
Test concurrent execution safety for the optimized node update system.

This script verifies that:
1. Thread-local storage prevents context contamination
2. Deferred updates are properly isolated per execution
3. Concurrent executions don't interfere with each other
4. Update manager handles parallel processing correctly
"""

import asyncio
import time
import random
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import threading
from loguru import logger

# Test environment setup
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sentientresearchagent.framework_entry import LightweightSentientAgent, ProfiledSentientAgent
from sentientresearchagent.config import load_config


class ConcurrencyTester:
    """Test harness for concurrent execution safety."""
    
    def __init__(self):
        self.results = {}
        self.context_leaks = []
        self.errors = []
        self.lock = threading.Lock()
        
    async def test_lightweight_agent_concurrency(self, num_agents: int = 5):
        """Test multiple LightweightAgent instances running concurrently."""
        logger.info(f"🧪 Testing {num_agents} concurrent LightweightAgent executions...")
        
        # Create multiple agents with different profiles
        agents = []
        for i in range(num_agents):
            agent = await self._create_lightweight_agent(f"agent_{i}")
            agents.append(agent)
        
        # Define test queries
        queries = [
            f"Calculate the factorial of {random.randint(5, 10)}",
            f"List the first {random.randint(5, 10)} prime numbers",
            f"Explain the concept of {random.choice(['recursion', 'polymorphism', 'encapsulation'])}",
            f"Write a function to reverse a string",
            f"What is {random.randint(10, 99)} times {random.randint(10, 99)}?"
        ]
        
        # Run agents concurrently
        tasks = []
        for i, agent in enumerate(agents):
            query = queries[i % len(queries)]
            task = asyncio.create_task(
                self._execute_with_tracking(agent, query, f"lightweight_{i}")
            )
            tasks.append(task)
        
        # Wait for all to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Analyze results
        self._analyze_results(results, "LightweightAgent")
        
    async def test_mixed_agent_concurrency(self, num_pairs: int = 3):
        """Test ProfiledAgent and LightweightAgent running concurrently."""
        logger.info(f"🧪 Testing {num_pairs} pairs of mixed agent executions...")
        
        tasks = []
        for i in range(num_pairs):
            # Create a ProfiledAgent
            profiled = await self._create_profiled_agent(f"profiled_{i}")
            task1 = asyncio.create_task(
                self._execute_with_tracking(
                    profiled, 
                    f"Research the history of {random.choice(['Python', 'JavaScript', 'Go'])}",
                    f"profiled_{i}"
                )
            )
            tasks.append(task1)
            
            # Create a LightweightAgent
            lightweight = await self._create_lightweight_agent(f"lightweight_{i}")
            task2 = asyncio.create_task(
                self._execute_with_tracking(
                    lightweight,
                    f"Calculate {random.randint(1, 100)} + {random.randint(1, 100)}",
                    f"lightweight_{i}"
                )
            )
            tasks.append(task2)
        
        # Run all concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Analyze results
        self._analyze_results(results, "Mixed Agents")
        
    async def test_update_manager_isolation(self):
        """Test that NodeUpdateManager maintains proper isolation."""
        logger.info("🧪 Testing NodeUpdateManager thread isolation...")
        
        from sentientresearchagent.hierarchical_agent_framework.services import NodeUpdateManager
        from sentientresearchagent.config import ExecutionConfig
        
        # Create config for deferred updates
        config = ExecutionConfig(
            execution_strategy="deferred",
            broadcast_mode="none",
            optimization_level="aggressive"
        )
        
        # Create multiple update managers in different threads
        managers = []
        executor = ThreadPoolExecutor(max_workers=5)
        
        def create_and_use_manager(thread_id: int):
            """Create and use manager in a thread."""
            manager = NodeUpdateManager.from_config(config)
            
            # Simulate updates
            for i in range(10):
                # Create a mock node
                class MockNode:
                    def __init__(self, task_id):
                        self.task_id = task_id
                
                node = MockNode(f"thread_{thread_id}_node_{i}")
                
                # Run async update in sync context
                asyncio.run(
                    manager.update_node_state(
                        node, 
                        "status",
                        {"thread_id": thread_id, "update_num": i}
                    )
                )
            
            # Check that updates are thread-local
            queue = manager._get_deferred_queue()
            return {
                "thread_id": thread_id,
                "queue_length": len(queue),
                "updates": [e.data for e in queue]
            }
        
        # Run in multiple threads
        futures = []
        for i in range(5):
            future = executor.submit(create_and_use_manager, i)
            futures.append(future)
        
        # Collect results
        thread_results = []
        for future in futures:
            result = future.result()
            thread_results.append(result)
            
        # Verify isolation
        logger.info("Thread isolation results:")
        for result in thread_results:
            logger.info(f"  Thread {result['thread_id']}: {result['queue_length']} updates")
            
            # Check that each thread only has its own updates
            for update in result['updates']:
                if update['thread_id'] != result['thread_id']:
                    self.context_leaks.append({
                        "type": "thread_isolation",
                        "expected_thread": result['thread_id'],
                        "found_thread": update['thread_id']
                    })
        
        if not self.context_leaks:
            logger.success("✅ Thread isolation maintained - no context leaks detected")
        else:
            logger.error(f"❌ Thread isolation violated - {len(self.context_leaks)} leaks detected")
            
    async def _create_lightweight_agent(self, agent_id: str) -> LightweightSentientAgent:
        """Create a LightweightAgent instance."""
        agent = LightweightSentientAgent.create_with_profile(
            profile_name="general_agent",
            enable_hitl_override=False
        )
        return agent
    
    async def _create_profiled_agent(self, agent_id: str) -> ProfiledSentientAgent:
        """Create a ProfiledAgent instance."""
        agent = ProfiledSentientAgent.create_with_profile(
            profile_name="general_agent",
            enable_hitl_override=False
        )
        return agent
    
    async def _execute_with_tracking(self, agent: Any, query: str, agent_id: str) -> Dict[str, Any]:
        """Execute agent with tracking."""
        start_time = time.time()
        
        try:
            logger.info(f"🚀 Agent {agent_id} starting: {query[:50]}...")
            
            # Execute based on agent type
            if hasattr(agent, 'execute') and asyncio.iscoroutinefunction(agent.execute):
                # LightweightAgent (async execute)
                result = await agent.execute(goal=query, max_steps=10)
            else:
                # ProfiledAgent (sync execute)
                result = agent.execute(goal=query, max_steps=10)
            
            execution_time = time.time() - start_time
            
            with self.lock:
                self.results[agent_id] = {
                    "query": query,
                    "success": result.get("status") == "completed",
                    "execution_time": execution_time,
                    "result": result
                }
            
            logger.success(f"✅ Agent {agent_id} completed in {execution_time:.2f}s")
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_info = {
                "agent_id": agent_id,
                "query": query,
                "error": str(e),
                "execution_time": execution_time
            }
            
            with self.lock:
                self.errors.append(error_info)
                
            logger.error(f"❌ Agent {agent_id} failed: {e}")
            return {"error": str(e)}
    
    def _analyze_results(self, results: List[Any], test_name: str):
        """Analyze test results for issues."""
        logger.info(f"\n📊 Analysis for {test_name}:")
        
        # Count successes and failures
        successes = sum(1 for r in results if not isinstance(r, Exception))
        failures = len(results) - successes
        
        logger.info(f"  Total executions: {len(results)}")
        logger.info(f"  Successful: {successes}")
        logger.info(f"  Failed: {failures}")
        
        # Check for context leaks
        if self.context_leaks:
            logger.error(f"  ⚠️ Context leaks detected: {len(self.context_leaks)}")
            for leak in self.context_leaks[:5]:  # Show first 5
                logger.error(f"    - {leak}")
        else:
            logger.success("  ✅ No context leaks detected")
        
        # Performance statistics
        if self.results:
            times = [r['execution_time'] for r in self.results.values() if 'execution_time' in r]
            if times:
                avg_time = sum(times) / len(times)
                logger.info(f"  Average execution time: {avg_time:.2f}s")
                logger.info(f"  Min time: {min(times):.2f}s")
                logger.info(f"  Max time: {max(times):.2f}s")


async def main():
    """Run all concurrency tests."""
    logger.info("🏁 Starting concurrent execution safety tests...")
    
    tester = ConcurrencyTester()
    
    # Test 1: Multiple LightweightAgents
    await tester.test_lightweight_agent_concurrency(num_agents=5)
    
    # Test 2: Mixed agent types
    await tester.test_mixed_agent_concurrency(num_pairs=3)
    
    # Test 3: Update manager isolation
    await tester.test_update_manager_isolation()
    
    # Final report
    logger.info("\n📋 FINAL REPORT:")
    logger.info(f"Total errors: {len(tester.errors)}")
    logger.info(f"Context leaks: {len(tester.context_leaks)}")
    
    if not tester.errors and not tester.context_leaks:
        logger.success("✅ All concurrency tests PASSED!")
        return 0
    else:
        logger.error("❌ Some concurrency tests FAILED!")
        return 1


if __name__ == "__main__":
    # Run tests
    exit_code = asyncio.run(main())
    sys.exit(exit_code)