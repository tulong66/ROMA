"""
TaskScheduler - Determines which nodes are ready for execution.

Responsibilities:
- Track node dependencies
- Determine execution readiness
- Manage execution order
- Handle parallel execution constraints
"""

from typing import List, Set, Dict, Optional, TYPE_CHECKING
from loguru import logger

from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskStatus
from sentientresearchagent.hierarchical_agent_framework.types import is_terminal_status

if TYPE_CHECKING:
    from sentientresearchagent.hierarchical_agent_framework.graph.task_graph import TaskGraph
    from sentientresearchagent.hierarchical_agent_framework.graph.state_manager import StateManager


class TaskScheduler:
    """
    Schedules tasks for execution based on dependencies and readiness.
    
    This class encapsulates all logic for determining which nodes should
    be executed next, respecting dependencies and parallel execution limits.
    """
    
    def __init__(self, task_graph: "TaskGraph", state_manager: "StateManager"):
        """
        Initialize the TaskScheduler.
        
        Args:
            task_graph: The task graph containing all nodes
            state_manager: Manages node state transitions
        """
        self.task_graph = task_graph
        self.state_manager = state_manager
        
        # Cache for performance
        self._dependency_cache: Dict[str, Set[str]] = {}
        self._last_cache_update = 0
        
        logger.info("TaskScheduler initialized")
    
    async def get_ready_nodes(self, max_nodes: Optional[int] = None) -> List[TaskNode]:
        """
        Get nodes that are ready for execution.
        
        A node is ready if:
        - It's in READY status
        - All its dependencies are satisfied
        - Its parent (if any) is in an appropriate state
        
        Args:
            max_nodes: Maximum number of nodes to return (for controlling parallelism)
            
        Returns:
            List of nodes ready for execution
        """
        ready_nodes = []
        
        # Get all nodes in READY or AGGREGATING status
        all_nodes = self.task_graph.get_all_nodes()
        potential_ready = [node for node in all_nodes if node.status in [TaskStatus.READY, TaskStatus.AGGREGATING]]
        
        # Check each potential node
        for node in potential_ready:
            if await self._is_node_executable(node):
                ready_nodes.append(node)
                
                # Check if we've reached the limit
                if max_nodes and len(ready_nodes) >= max_nodes:
                    break
        
        # Sort by priority (layer, then creation time)
        ready_nodes.sort(key=lambda n: (n.layer, n.timestamp_created))
        
        logger.info(f"TaskScheduler: {len(ready_nodes)} nodes ready for execution")
        return ready_nodes
    
    async def get_active_nodes(self) -> List[TaskNode]:
        """
        Get all nodes that are currently active (not in terminal state).
        
        Returns:
            List of active nodes
        """
        all_nodes = self.task_graph.get_all_nodes()
        active_nodes = [
            node for node in all_nodes 
            if not is_terminal_status(node.status)
        ]
        
        return active_nodes
    
    async def get_pending_nodes(self) -> List[TaskNode]:
        """
        Get nodes that are pending execution.
        
        Returns:
            List of pending nodes with their blocking reasons
        """
        all_nodes = self.task_graph.get_all_nodes()
        pending_nodes = []
        
        for node in all_nodes:
            if node.status == TaskStatus.PENDING:
                # Analyze why the node is pending
                blocking_reason = await self._get_blocking_reason(node)
                node.aux_data["blocking_reason"] = blocking_reason
                pending_nodes.append(node)
        
        return pending_nodes
    
    async def update_node_readiness(self) -> int:
        """
        Update the readiness status of all nodes.
        
        This method transitions PENDING nodes to READY when their
        dependencies are satisfied.
        
        Returns:
            Number of nodes transitioned to READY
        """
        transitioned = 0
        all_nodes = self.task_graph.get_all_nodes()
        
        for node in all_nodes:
            if node.status == TaskStatus.PENDING:
                if await self._can_transition_to_ready(node):
                    # Transition the node to READY
                    old_status = node.status
                    node.update_status(TaskStatus.READY, validate_transition=True)
                    
                    # Update in knowledge store if we have one
                    # Note: TaskScheduler doesn't have direct access to knowledge store
                    # This should be handled by the caller
                    
                    transitioned += 1
                    logger.info(f"Node {node.task_id} transitioned from PENDING to READY")
        
        if transitioned > 0:
            logger.info(f"TaskScheduler: {transitioned} nodes transitioned to READY")
        
        return transitioned
    
    async def _is_node_executable(self, node: TaskNode) -> bool:
        """
        Check if a node is truly ready for execution.
        
        Args:
            node: Node to check
            
        Returns:
            True if node can be executed now
        """
        # Node must be in READY or AGGREGATING status
        if node.status not in [TaskStatus.READY, TaskStatus.AGGREGATING]:
            return False
        
        # AGGREGATING nodes are always executable (they've already checked children)
        if node.status == TaskStatus.AGGREGATING:
            return True
        
        # Check parent readiness
        if not await self._is_parent_ready(node):
            return False
        
        # Check dependencies
        if not await self._are_dependencies_satisfied(node):
            return False
        
        # Check resource constraints (future enhancement)
        # if not await self._has_required_resources(node):
        #     return False
        
        return True
    
    async def _is_parent_ready(self, node: TaskNode) -> bool:
        """
        Check if a node's parent is in an appropriate state.
        
        Args:
            node: Node to check
            
        Returns:
            True if parent is ready or node has no parent
        """
        if not node.parent_node_id:
            return True
        
        parent = self.task_graph.get_node(node.parent_node_id)
        if not parent:
            logger.warning(f"Node {node.task_id} has invalid parent {node.parent_node_id}")
            return False
        
        # Parent must be RUNNING or PLAN_DONE for child to execute
        return parent.status in [TaskStatus.RUNNING, TaskStatus.PLAN_DONE]
    
    async def _are_dependencies_satisfied(self, node: TaskNode) -> bool:
        """
        Check if all node dependencies are satisfied.
        
        Args:
            node: Node to check
            
        Returns:
            True if all dependencies are satisfied
        """
        # Get node dependencies
        dependencies = await self._get_node_dependencies(node)
        
        # Log dependencies for debugging
        if dependencies:
            logger.debug(f"Node {node.task_id} has dependencies: {dependencies}")
        
        # Check each dependency
        for dep_id in dependencies:
            dep_node = self.task_graph.get_node(dep_id)
            if not dep_node:
                logger.warning(f"Node {node.task_id} has invalid dependency {dep_id}")
                continue
            
            # Dependency must be in terminal success state
            if dep_node.status != TaskStatus.DONE:
                logger.debug(f"Node {node.task_id} waiting for dependency {dep_id} (status: {dep_node.status})")
                return False
        
        # All dependencies satisfied
        if dependencies:
            logger.info(f"All dependencies satisfied for node {node.task_id}")
        
        return True
    
    async def _get_node_dependencies(self, node: TaskNode) -> Set[str]:
        """
        Get all dependencies for a node.
        
        Args:
            node: Node to get dependencies for
            
        Returns:
            Set of dependency node IDs
        """
        # Check cache first
        if node.task_id in self._dependency_cache:
            return self._dependency_cache[node.task_id]
        
        dependencies = set()
        
        # Method 1: Check aux_data for depends_on_indices (more reliable for newly created nodes)
        depends_on_indices = node.aux_data.get('depends_on_indices', []) if node.aux_data is not None else []
        if depends_on_indices and node.parent_node_id:
            # Get sibling nodes to resolve indices to IDs
            parent = self.task_graph.get_node(node.parent_node_id)
            if parent and parent.planned_sub_task_ids:
                for dep_idx in depends_on_indices:
                    if 0 <= dep_idx < len(parent.planned_sub_task_ids):
                        dep_id = parent.planned_sub_task_ids[dep_idx]
                        dependencies.add(dep_id)
                        logger.debug(f"Found dependency {dep_id} for node {node.task_id} from aux_data")
        
        # Method 2: Find the graph containing this node and check graph edges
        container_graph_id = None
        for graph_id, graph in self.task_graph.graphs.items():
            if node.task_id in graph.nodes:
                container_graph_id = graph_id
                break
        
        if container_graph_id:
            # Get predecessors in the graph
            predecessors = self.task_graph.get_node_predecessors(
                container_graph_id, 
                node.task_id
            )
            for pred in predecessors:
                dependencies.add(pred.task_id)
                logger.debug(f"Found dependency {pred.task_id} for node {node.task_id} from graph")
        
        # Cache the result
        self._dependency_cache[node.task_id] = dependencies
        
        return dependencies
    
    async def _can_transition_to_ready(self, node: TaskNode) -> bool:
        """
        Check if a PENDING node can transition to READY.
        
        Args:
            node: Node to check
            
        Returns:
            True if node can transition to READY
        """
        # Must be PENDING
        if node.status != TaskStatus.PENDING:
            return False
        
        # Check parent conditions
        if node.parent_node_id:
            parent = self.task_graph.get_node(node.parent_node_id)
            if not parent:
                return False
            
            # Parent must be in appropriate state
            if parent.status not in [TaskStatus.RUNNING, TaskStatus.PLAN_DONE, TaskStatus.DONE]:
                return False
        
        # Check dependencies
        return await self._are_dependencies_satisfied(node)
    
    async def _get_blocking_reason(self, node: TaskNode) -> str:
        """
        Get the reason why a node is blocked from execution.
        
        Args:
            node: Node to analyze
            
        Returns:
            Human-readable blocking reason
        """
        reasons = []
        
        # Check parent status
        if node.parent_node_id:
            parent = self.task_graph.get_node(node.parent_node_id)
            if parent:
                if parent.status not in [TaskStatus.RUNNING, TaskStatus.PLAN_DONE, TaskStatus.DONE]:
                    reasons.append(f"Parent {parent.task_id} is in {parent.status} state")
            else:
                reasons.append(f"Parent {node.parent_node_id} not found")
        
        # Check dependencies
        dependencies = await self._get_node_dependencies(node)
        incomplete_deps = []
        
        for dep_id in dependencies:
            dep_node = self.task_graph.get_node(dep_id)
            if dep_node and dep_node.status != TaskStatus.DONE:
                incomplete_deps.append(f"{dep_id} ({dep_node.status})")
        
        if incomplete_deps:
            reasons.append(f"Waiting for dependencies: {', '.join(incomplete_deps)}")
        
        return "; ".join(reasons) if reasons else "Unknown"
    
    def clear_dependency_cache(self):
        """Clear the dependency cache (call when graph structure changes)."""
        self._dependency_cache.clear()
        logger.debug("TaskScheduler: Dependency cache cleared")
    
    def get_execution_metrics(self) -> Dict[str, int]:
        """
        Get metrics about the current execution state.
        
        Returns:
            Dictionary with execution metrics
        """
        all_nodes = self.task_graph.get_all_nodes()
        
        metrics = {
            "total_nodes": len(all_nodes),
            "pending": sum(1 for n in all_nodes if n.status == TaskStatus.PENDING),
            "ready": sum(1 for n in all_nodes if n.status == TaskStatus.READY),
            "running": sum(1 for n in all_nodes if n.status == TaskStatus.RUNNING),
            "completed": sum(1 for n in all_nodes if n.status == TaskStatus.DONE),
            "failed": sum(1 for n in all_nodes if n.status == TaskStatus.FAILED),
            "plan_done": sum(1 for n in all_nodes if n.status == TaskStatus.PLAN_DONE),
            "aggregating": sum(1 for n in all_nodes if n.status == TaskStatus.AGGREGATING),
            "needs_replan": sum(1 for n in all_nodes if n.status == TaskStatus.NEEDS_REPLAN),
        }
        
        return metrics