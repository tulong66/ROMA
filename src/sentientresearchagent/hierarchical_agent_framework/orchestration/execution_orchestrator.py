"""
ExecutionOrchestrator - High-level orchestration of task execution.

This replaces the monolithic ExecutionEngine with a cleaner, more focused design.
Responsibilities:
- Orchestrate the overall execution flow
- Coordinate between different services
- Manage the execution lifecycle
"""

from typing import Optional, Dict, Any, TYPE_CHECKING
from loguru import logger
from pathlib import Path
import asyncio

from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskStatus, TaskType, NodeType
from sentientresearchagent.exceptions import SentientError

if TYPE_CHECKING:
    from sentientresearchagent.hierarchical_agent_framework.graph.task_graph import TaskGraph
    from sentientresearchagent.hierarchical_agent_framework.graph.state_manager import StateManager
    from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import KnowledgeStore
    from sentientresearchagent.hierarchical_agent_framework.node.node_processor import NodeProcessor
    from sentientresearchagent.config import SentientConfig
    from .task_scheduler import TaskScheduler
    from .deadlock_detector import DeadlockDetector
    from .recovery_manager import RecoveryManager
    from ..persistence.checkpoint_manager import CheckpointManager


class ExecutionOrchestrator:
    """
    High-level orchestrator for task execution.
    
    This class coordinates between different services to execute a task graph.
    It delegates specific responsibilities to specialized components.
    """
    
    def __init__(
        self,
        task_graph: "TaskGraph",
        state_manager: "StateManager",
        knowledge_store: "KnowledgeStore",
        node_processor: "NodeProcessor",
        config: "SentientConfig",
        task_scheduler: Optional["TaskScheduler"] = None,
        deadlock_detector: Optional["DeadlockDetector"] = None,
        recovery_manager: Optional["RecoveryManager"] = None,
        checkpoint_manager: Optional["CheckpointManager"] = None,
    ):
        """
        Initialize the ExecutionOrchestrator.
        
        Args:
            task_graph: The task graph to execute
            state_manager: Manages state transitions
            knowledge_store: Stores execution knowledge
            node_processor: Processes individual nodes
            config: System configuration
            task_scheduler: Schedules tasks for execution (will create if not provided)
            deadlock_detector: Detects deadlocks (will create if not provided)
            recovery_manager: Manages error recovery (will create if not provided)
            checkpoint_manager: Manages checkpoints (optional)
        """
        self.task_graph = task_graph
        self.state_manager = state_manager
        self.knowledge_store = knowledge_store
        self.node_processor = node_processor
        self.config = config
        
        # Create default components if not provided
        if not task_scheduler:
            from .task_scheduler import TaskScheduler
            self.task_scheduler = TaskScheduler(task_graph, state_manager)
        else:
            self.task_scheduler = task_scheduler
            
        if not deadlock_detector:
            from .deadlock_detector import DeadlockDetector
            self.deadlock_detector = DeadlockDetector(task_graph, state_manager)
        else:
            self.deadlock_detector = deadlock_detector
            
        if not recovery_manager:
            from .recovery_manager import RecoveryManager
            self.recovery_manager = RecoveryManager(config)
        else:
            self.recovery_manager = recovery_manager
            
        self.checkpoint_manager = checkpoint_manager
        
        # Execution state
        self._execution_id: Optional[str] = None
        self._is_running = False
        self._execution_stats = {
            "steps_executed": 0,
            "nodes_processed": 0,
            "errors_recovered": 0,
            "checkpoints_created": 0
        }
        
        logger.info("ExecutionOrchestrator initialized")
    
    async def execute(
        self, 
        root_goal: str,
        max_steps: Optional[int] = None,
        execution_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a task graph starting from a root goal.
        
        Args:
            root_goal: The main goal to achieve
            max_steps: Maximum execution steps (uses config default if not specified)
            execution_id: Optional execution ID for tracking
            
        Returns:
            Execution result dictionary
        """
        if self._is_running:
            raise SentientError("Execution already in progress")
            
        self._is_running = True
        self._execution_id = execution_id or self._generate_execution_id()
        
        logger.info(f"Starting execution {self._execution_id}: {root_goal}")
        
        try:
            # Initialize the root task
            root_node = await self._initialize_root_task(root_goal)
            if not root_node:
                return {"error": "Failed to initialize root task"}
            
            # Run the execution loop
            max_steps = max_steps or self.config.execution.max_execution_steps
            result = await self._execution_loop(max_steps)
            
            # Finalize execution
            final_result = await self._finalize_execution(result)
            
            logger.info(f"Execution {self._execution_id} completed")
            return final_result
            
        except Exception as e:
            logger.error(f"Execution {self._execution_id} failed: {e}")
            return {
                "error": str(e),
                "execution_id": self._execution_id,
                "stats": self._execution_stats
            }
        finally:
            self._is_running = False
    
    async def _initialize_root_task(self, root_goal: str) -> Optional[TaskNode]:
        """Initialize the root task node."""
        try:
            # Create root node
            root_node = TaskNode(
                goal=root_goal,
                task_type=TaskType.WRITE,  # Default, can be customized
                node_type=NodeType.PLAN,   # Root typically starts with planning
                layer=0,
                task_id="root",
                overall_objective=root_goal
            )
            
            # Add to task graph
            root_graph_id = "root_graph"
            self.task_graph.add_graph(root_graph_id, is_root=True)
            self.task_graph.add_node_to_graph(root_graph_id, root_node)
            self.task_graph.overall_project_goal = root_goal
            
            # Log to knowledge store
            self.knowledge_store.add_or_update_record_from_node(root_node)
            
            # Transition root node to READY
            root_node.update_status(TaskStatus.READY, validate_transition=True)
            
            logger.info(f"Initialized root task: {root_node.task_id}")
            return root_node
            
        except Exception as e:
            logger.error(f"Failed to initialize root task: {e}")
            return None
    
    async def _execution_loop(self, max_steps: int) -> Dict[str, Any]:
        """
        Main execution loop.
        
        Args:
            max_steps: Maximum number of steps to execute
            
        Returns:
            Execution result
        """
        import time
        start_time = time.time()
        
        logger.info("=" * 80)
        logger.info("🚀 EXECUTION FLOW STARTED")
        logger.info(f"⏱️ EXECUTION TIMEOUT: {self.config.execution.node_execution_timeout_seconds} seconds")
        logger.info("=" * 80)
        
        for step in range(max_steps):
            self._execution_stats["steps_executed"] += 1
            
            # Check timeout
            elapsed_time = time.time() - start_time
            if elapsed_time > self.config.execution.node_execution_timeout_seconds:
                logger.error(f"Execution timeout after {elapsed_time:.2f}s")
                return {"error": f"Execution timeout after {elapsed_time:.2f}s"}
            
            # Log step header with node summary
            all_nodes = self.task_graph.get_all_nodes()
            status_summary = {}
            for node in all_nodes:
                status_name = node.status.name
                status_summary[status_name] = status_summary.get(status_name, 0) + 1
            
            logger.info(f"\n📍 Step {step + 1}/{max_steps} | Time: {elapsed_time:.1f}s | Nodes: {status_summary}")
            
            # Update node readiness (transitions PENDING to READY when dependencies satisfied)
            transitioned = await self.task_scheduler.update_node_readiness()
            if transitioned > 0:
                logger.info(f"✅ PENDING → READY: {transitioned} nodes transitioned")
                # Update knowledge store for all newly ready nodes
                for node in self.task_graph.get_all_nodes():
                    if node.status == TaskStatus.READY:
                        self.knowledge_store.add_or_update_record_from_node(node)
            
            # Check for nodes ready to aggregate (PLAN_DONE -> AGGREGATING)
            # Keep checking until no more transitions are possible (handles async subtask completion)
            aggregated_total = 0
            max_aggregate_iterations = 5
            
            for agg_iter in range(max_aggregate_iterations):
                aggregated_this_iter = 0
                all_nodes = self.task_graph.get_all_nodes()
                plan_done_nodes = [n for n in all_nodes if n.status == TaskStatus.PLAN_DONE]
                
                if not plan_done_nodes:
                    break
                    
                for node in plan_done_nodes:
                    if self.state_manager.can_aggregate(node):
                        # Transition to AGGREGATING
                        try:
                            node.update_status(TaskStatus.AGGREGATING, validate_transition=True)
                            self.knowledge_store.add_or_update_record_from_node(node)
                            aggregated_this_iter += 1
                            logger.info(f"✅ PLAN_DONE → AGGREGATING: {node.task_id} (all subtasks complete)")
                        except Exception as e:
                            logger.warning(f"Failed to transition {node.task_id} to AGGREGATING: {e}")
                
                aggregated_total += aggregated_this_iter
                
                # If no transitions this iteration, stop checking
                if aggregated_this_iter == 0:
                    break
                    
                # Small delay to allow async operations to complete
                await asyncio.sleep(0.05)
            
            if aggregated_total > 0:
                logger.info(f"📊 Aggregation: {aggregated_total} nodes ready to aggregate results")
            
            # IMPROVED CONCURRENCY: Get currently running nodes and available slots
            all_nodes = self.task_graph.get_all_nodes()
            running_nodes = [n for n in all_nodes if n.status == TaskStatus.RUNNING]
            max_concurrent = getattr(self.config.execution, 'max_concurrent_nodes', 2)
            available_slots = max_concurrent - len(running_nodes)
            
            logger.debug(f"🔄 CONCURRENCY: {len(running_nodes)} running, {available_slots} slots available (max: {max_concurrent})")
            
            # Get next tasks to execute (only as many as we have slots for)
            ready_nodes = await self.task_scheduler.get_ready_nodes()
            
            if not ready_nodes:
                # Check if execution is complete
                if await self._is_execution_complete():
                    logger.info("=" * 80)
                    logger.info("✅ EXECUTION COMPLETE - All tasks finished")
                    logger.info("=" * 80)
                    break
                
                # Check for deadlock
                deadlock_info = await self.deadlock_detector.detect_deadlock()
                if deadlock_info["is_deadlocked"]:
                    # Try recovery
                    recovery_result = await self._attempt_deadlock_recovery(deadlock_info)
                    if not recovery_result["recovered"]:
                        logger.error(f"Deadlock detected and recovery failed: {deadlock_info['reason']}")
                        return {"error": f"Deadlock: {deadlock_info['reason']}"}
                    else:
                        logger.info(f"Recovered from deadlock: {recovery_result['action']}")
                        continue
                else:
                    # No tasks ready but not deadlocked - wait briefly
                    await asyncio.sleep(0.1)
                    continue
            
            # Limit nodes to process based on available slots
            nodes_to_process = ready_nodes[:available_slots] if available_slots > 0 else []
            
            if not nodes_to_process:
                # All slots filled, wait briefly for nodes to complete
                logger.debug(f"🔄 CONCURRENCY: All {max_concurrent} slots occupied, waiting for completion")
                await asyncio.sleep(0.1)
                continue
            
            # Process ready nodes (only up to available slots)
            processed_count = await self._process_nodes(nodes_to_process)
            self._execution_stats["nodes_processed"] += processed_count
            
            # IMMEDIATE AGGREGATION CHECK: Check if any nodes completed and triggered parent aggregation
            if processed_count > 0:
                immediate_aggregation_count = await self._check_immediate_aggregation_triggers()
                if immediate_aggregation_count > 0:
                    logger.info(f"🚀 IMMEDIATE AGGREGATION: {immediate_aggregation_count} parents checked due to child completion")
            
            # Clear dependency cache after processing nodes (graph may have changed)
            if processed_count > 0:
                self.task_scheduler.clear_dependency_cache()
            
            # Create checkpoint if needed
            if self.checkpoint_manager and self.checkpoint_manager.should_checkpoint():
                await self._create_checkpoint(step)
        
        # Check if we hit max steps
        if step >= max_steps - 1:
            active_nodes = await self.task_scheduler.get_active_nodes()
            if active_nodes:
                logger.warning(f"Reached max steps with {len(active_nodes)} active nodes")
                return {"error": f"Reached max steps ({max_steps}) with active nodes remaining"}
        
        return {"success": True}
    
    async def _process_nodes(self, nodes: list[TaskNode]) -> int:
        """
        Process a batch of nodes.
        
        Args:
            nodes: Nodes to process
            
        Returns:
            Number of nodes successfully processed
        """
        processed = 0
        
        # Process nodes concurrently with controlled parallelism
        max_parallel = getattr(self.config.execution, 'max_parallel_nodes', self.config.execution.max_concurrent_nodes)
        
        for i in range(0, len(nodes), max_parallel):
            batch = nodes[i:i + max_parallel]
            
            # Create processing tasks
            tasks = []
            for node in batch:
                task = self._process_single_node(node)
                tasks.append(task)
            
            # Wait for batch to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Count successful processings
            for result in results:
                if not isinstance(result, Exception):
                    processed += 1
                else:
                    logger.error(f"Node processing failed: {result}")
        
        return processed
    
    async def _check_immediate_aggregation_triggers(self) -> int:
        """
        Check for immediate aggregation triggers from recently completed child nodes.
        This provides faster response than waiting for the next cycle iteration.
        
        Returns:
            Number of parent nodes checked for immediate aggregation
        """
        checked_parents = 0
        
        # Get all nodes and check for aggregation triggers
        all_nodes = self.task_graph.get_all_nodes()
        
        for node in all_nodes:
            # Check if this node has an aggregation trigger in its aux_data
            if (hasattr(node, 'aux_data') and node.aux_data and 
                'trigger_parent_aggregation_check' in node.aux_data):
                
                trigger_info = node.aux_data['trigger_parent_aggregation_check']
                parent_id = trigger_info.get('parent_id')
                child_id = trigger_info.get('child_id')
                
                if parent_id:
                    parent_node = self.task_graph.get_node(parent_id)
                    if parent_node and parent_node.status == TaskStatus.PLAN_DONE:
                        logger.info(f"🔍 IMMEDIATE CHECK: Child {child_id} completed, checking if parent {parent_id} can aggregate")
                        
                        # Check if parent can now aggregate
                        if self.state_manager.can_aggregate(parent_node):
                            try:
                                parent_node.update_status(TaskStatus.AGGREGATING, validate_transition=True)
                                self.knowledge_store.add_or_update_record_from_node(parent_node)
                                logger.info(f"✅ IMMEDIATE AGGREGATION: Parent {parent_id} transitioned to AGGREGATING due to child {child_id} completion")
                                checked_parents += 1
                            except Exception as e:
                                logger.warning(f"Failed immediate aggregation transition for {parent_id}: {e}")
                        else:
                            logger.debug(f"Parent {parent_id} not ready to aggregate yet (other children still running)")
                    
                    # Clear the trigger to avoid duplicate processing
                    del node.aux_data['trigger_parent_aggregation_check']
        
        return checked_parents
    
    async def _process_single_node(self, node: TaskNode) -> bool:
        """
        Process a single node with error recovery.
        
        Args:
            node: Node to process
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Process the node
            await self.node_processor.process_node(
                node, 
                self.task_graph, 
                self.knowledge_store
            )
            return True
            
        except Exception as e:
            logger.error(f"Error processing node {node.task_id}: {e}")
            
            # Attempt recovery
            recovery_strategy = self.recovery_manager.get_strategy_for_error(e)
            if recovery_strategy:
                recovery_result = await recovery_strategy.recover(node, e)
                if recovery_result.recovered:
                    self._execution_stats["errors_recovered"] += 1
                    logger.info(f"Recovered from error in node {node.task_id}: {recovery_result.action}")
                    return True
            
            # Recovery failed - mark node as failed
            node.fail_with_error(e, {"recovery_attempted": True})
            self.knowledge_store.add_or_update_record_from_node(node)
            return False
    
    async def _is_execution_complete(self) -> bool:
        """Check if the execution is complete."""
        active_nodes = await self.task_scheduler.get_active_nodes()
        
        # Also check for PLAN_DONE nodes that might transition to AGGREGATING
        all_nodes = self.task_graph.get_all_nodes()
        plan_done_nodes = [n for n in all_nodes if n.status == TaskStatus.PLAN_DONE]
        
        # If there are PLAN_DONE nodes, check if any could potentially aggregate
        for node in plan_done_nodes:
            if self.state_manager.can_aggregate(node):
                # This node can still progress
                return False
                
        return len(active_nodes) == 0 and len(plan_done_nodes) == 0
    
    async def _attempt_deadlock_recovery(self, deadlock_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Attempt to recover from a deadlock.
        
        Args:
            deadlock_info: Information about the deadlock
            
        Returns:
            Recovery result with 'recovered' and 'action' keys
        """
        recovery_strategy = self.recovery_manager.get_deadlock_recovery_strategy()
        if recovery_strategy:
            result = await recovery_strategy.recover_from_deadlock(
                deadlock_info,
                self.task_graph,
                self.state_manager
            )
            if result["recovered"]:
                self._execution_stats["errors_recovered"] += 1
            return result
        
        return {"recovered": False, "action": "No recovery strategy available"}
    
    async def _create_checkpoint(self, step: int) -> None:
        """Create an execution checkpoint."""
        if not self.checkpoint_manager:
            return
            
        try:
            metadata = {
                "execution_id": self._execution_id,
                "step": step,
                "stats": self._execution_stats.copy()
            }
            
            self.checkpoint_manager.create_checkpoint(
                self.task_graph,
                self.knowledge_store,
                metadata
            )
            
            self._execution_stats["checkpoints_created"] += 1
            logger.info(f"Created checkpoint at step {step}")
            
        except Exception as e:
            logger.error(f"Failed to create checkpoint: {e}")
    
    async def _finalize_execution(self, execution_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Finalize the execution and prepare the result.
        
        Args:
            execution_result: Raw execution result
            
        Returns:
            Final execution result
        """
        # Get root node result
        root_node = self.task_graph.get_node("root")
        
        if not root_node:
            return {
                "error": "Root node not found",
                "execution_id": self._execution_id,
                "stats": self._execution_stats
            }
        
        # Prepare final result
        final_result = {
            "execution_id": self._execution_id,
            "status": "success" if execution_result.get("success") else "failed",
            "stats": self._execution_stats
        }
        
        if root_node.status == TaskStatus.DONE:
            final_result["result"] = root_node.result
            final_result["summary"] = root_node.output_summary
        elif root_node.status == TaskStatus.AGGREGATING:
            # For nodes that finished aggregation but didn't transition to DONE
            if root_node.result:
                final_result["result"] = root_node.result
                final_result["summary"] = root_node.output_summary or "Aggregation completed"
            else:
                final_result["error"] = "Node in AGGREGATING state but has no result"
        elif root_node.status == TaskStatus.FAILED:
            final_result["error"] = root_node.error or "Task failed"
        else:
            final_result["error"] = f"Unexpected final status: {root_node.status}"
        
        # Add any error from execution
        if "error" in execution_result:
            final_result["execution_error"] = execution_result["error"]
        
        return final_result
    
    def _generate_execution_id(self) -> str:
        """Generate a unique execution ID."""
        import uuid
        return f"exec_{uuid.uuid4().hex[:8]}"
    
    async def resume_from_checkpoint(
        self, 
        checkpoint_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Resume execution from a checkpoint.
        
        Args:
            checkpoint_path: Path to checkpoint file (uses latest if not specified)
            
        Returns:
            Execution result
        """
        if not self.checkpoint_manager:
            return {"error": "Checkpoint manager not configured"}
        
        # Load checkpoint
        checkpoint_data = self.checkpoint_manager.load_checkpoint(checkpoint_path)
        if not checkpoint_data:
            return {"error": "Failed to load checkpoint"}
        
        task_graph, knowledge_store, metadata = checkpoint_data
        
        # Update state
        self.task_graph = task_graph
        self.knowledge_store = knowledge_store
        self._execution_id = metadata.get("execution_id", self._generate_execution_id())
        self._execution_stats = metadata.get("stats", self._execution_stats)
        
        logger.info(f"Resumed from checkpoint at step {metadata.get('step', 'unknown')}")
        
        # Continue execution
        return await self._execution_loop(self.config.execution.max_execution_steps)
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get current execution statistics."""
        return self._execution_stats.copy()