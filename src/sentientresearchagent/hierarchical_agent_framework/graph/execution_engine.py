import time
from loguru import logger
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskStatus, NodeType, TaskType
from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import KnowledgeStore # For logging to KS
from sentientresearchagent.hierarchical_agent_framework.utils.hitl_utils import request_human_review
from sentientresearchagent.hierarchical_agent_framework.types import is_terminal_status

from typing import TYPE_CHECKING, List
if TYPE_CHECKING:
    from sentientresearchagent.hierarchical_agent_framework.graph.task_graph import TaskGraph
    from sentientresearchagent.hierarchical_agent_framework.graph.state_manager import StateManager
    from sentientresearchagent.hierarchical_agent_framework.node.node_processor import NodeProcessor
    from sentientresearchagent.hierarchical_agent_framework.node.hitl_coordinator import HITLCoordinator


from agno.exceptions import StopAgentRun # Added import
from typing import Optional, Callable, Dict
import pprint # For logging results
import asyncio # Import asyncio
import time  # For timeout tracking
from sentientresearchagent.exceptions import TaskTimeoutError, AgentExecutionError  # For error handling

# Import new ProjectInitializer
from .project_initializer import ProjectInitializer

# HITLCoordinator moved to TYPE_CHECKING to avoid circular import

# Import CycleManager
from .cycle_manager import CycleManager

# Import SentientConfig
from sentientresearchagent.config import SentientConfig

# ADDED: Import for NodeProcessorConfig creation if ExecutionEngine creates NodeProcessor
from sentientresearchagent.framework_entry import create_node_processor_config_from_main_config 


class ExecutionEngine:
    """Orchestrates the overall execution flow of tasks in the graph."""

    def __init__(self, 
                 task_graph: "TaskGraph",
                 state_manager: "StateManager",
                 knowledge_store: KnowledgeStore,
                 hitl_coordinator: "HITLCoordinator",
                 config: SentientConfig, # MODIFIED: Made SentientConfig non-optional
                 node_processor: Optional["NodeProcessor"] = None
                ):
        self.task_graph = task_graph
        self.config: SentientConfig = config # Store config
        self.node_start_times: Dict[str, float] = {}  # Track when nodes start processing
        self.stuck_node_attempts: Dict[str, int] = {}  # Track recovery attempts for stuck nodes
        
        if node_processor:
            self.node_processor = node_processor
            logger.info("ExecutionEngine initialized with provided NodeProcessor.")
        else:
            logger.warning("ExecutionEngine creating its own NodeProcessor instance (SystemManager should ideally provide one).")
            # NodeProcessor will load blueprint based on self.config.active_profile_name
            # It needs NodeProcessorConfig, derived from the main SentientConfig.
            from sentientresearchagent.hierarchical_agent_framework.node.node_processor import NodeProcessor
            from sentientresearchagent.hierarchical_agent_framework.tracing.manager import TraceManager
            from sentientresearchagent.hierarchical_agent_framework.agents.registry import AgentRegistry
            
            # Create temporary trace manager and agent registry for fallback NodeProcessor
            temp_trace_manager = TraceManager(project_id="execution_engine_fallback")
            temp_agent_registry = AgentRegistry()
            
            node_proc_config = create_node_processor_config_from_main_config(self.config)
            self.node_processor = NodeProcessor(
                task_graph=self.task_graph,
                knowledge_store=knowledge_store,
                agent_registry=temp_agent_registry,
                trace_manager=temp_trace_manager,
                config=self.config, 
                node_processor_config=node_proc_config,
                agent_blueprint=None # NodeProcessor will use active_profile_name from self.config
            )
            logger.info("ExecutionEngine created a new NodeProcessor.")
            
        self.state_manager = state_manager
        self.knowledge_store = knowledge_store 
        self.hitl_coordinator = hitl_coordinator 
        self.project_initializer = ProjectInitializer() 
        self.cycle_manager = CycleManager() 
        logger.info("ExecutionEngine initialized.")
        # self.node_processor.set_viz_handler(viz_handler) # If you re-add visualization

    def initialize_project(self, 
                           root_goal: str, 
                           root_task_type: TaskType = TaskType.WRITE, # Default, can be changed
                          ):
        """Sets up the initial root node for the project. HITL review for the root goal will be handled by _perform_root_node_hitl called separately."""
        if self.task_graph.root_graph_id is not None:
            logger.warning("Project already initialized or root graph exists.")
            return

        self.task_graph.overall_project_goal = root_goal
        
        root_node_id = "root" # Fixed ID for the ultimate root task
        root_graph_id = "root_graph" # Graph containing the root task

        # The root task usually starts as a PLAN to decompose the overall goal
        root_node = TaskNode(
            goal=root_goal,
            task_type=root_task_type, # This might often be a general "project" type
            node_type=NodeType.PLAN,  # Root usually starts by planning
            layer=0,
            task_id=root_node_id,
            overall_objective=root_goal # For root, objective is its own goal initially
        )
        
        self.task_graph.add_graph(root_graph_id, is_root=True)
        self.task_graph.add_node_to_graph(root_graph_id, root_node)
        self.knowledge_store.add_or_update_record_from_node(root_node) # Log initial node

        logger.success(f"Initialized with root node: {root_node.task_id} in graph {root_graph_id}. Root goal will be reviewed via HITL next.")

    async def _perform_root_node_hitl(self, root_node: TaskNode):
        """Performs HITL review for the root node's goal after initialization."""
        if not root_node or root_node.task_id != "root":
            logger.error("_perform_root_node_hitl called with invalid node.")
            return

        logger.info(f"ExecutionEngine: Triggering initial HITL review for root node {root_node.task_id}.")
        try:
            hitl_outcome = await request_human_review(
                checkpoint_name="RootNodeGoalReview",
                context_message=f"Review initial root task goal: '{root_node.goal}'. You can approve or provide a modified goal as modification instructions.",
                data_for_review=root_node.model_dump(), 
                node_id=root_node.task_id,
            )

            if hitl_outcome.get("user_choice") == "approved":
                logger.info(f"Root node {root_node.task_id} goal approved by user without changes.")
            elif hitl_outcome.get("user_choice") == "request_modification":
                modified_goal = hitl_outcome.get("modification_instructions", "").strip()
                if modified_goal:
                    logger.info(f"Root node {root_node.task_id} goal modified by user: '{root_node.goal}' -> '{modified_goal}'")
                    root_node.goal = modified_goal
                    self.task_graph.overall_project_goal = modified_goal 
                    self.knowledge_store.add_or_update_record_from_node(root_node)
                else:
                    logger.info(f"Root node {root_node.task_id} goal approved by user (modification requested but no instructions given, using original).")
            else: # "aborted" or other error from HITL
                logger.warning(f"Root node {root_node.task_id} review resulted in '{hitl_outcome.get('user_choice', 'unknown outcome')}' with message: '{hitl_outcome.get('message', '')}'.")
                if hitl_outcome.get("user_choice") == "aborted": # Check if StopAgentRun was caught by HITL util and reported as "aborted"
                    root_node.update_status(TaskStatus.CANCELLED, result_summary=f"Cancelled by user at initial review: {hitl_outcome.get('message', '')}")
                    self.knowledge_store.add_or_update_record_from_node(root_node)
                    logger.info(f"Root node {root_node.task_id} status set to CANCELLED due to HITL abort.")
                # If not explicitly aborted, the node remains PENDING (its initial status after creation) or whatever status it had.
                # The run_cycle will then pick it up. If it's PENDING, it will transition to READY.
        except Exception as e: # Catch any other unexpected error during HITL
            logger.exception(f"Error during _perform_root_node_hitl for {root_node.task_id}: {e}")
            root_node.update_status(TaskStatus.FAILED, error_msg=f"Error during initial HITL review: {e}")
            self.knowledge_store.add_or_update_record_from_node(root_node)

    async def run_project_flow(self, root_goal: str, root_task_type: TaskType = TaskType.WRITE, max_steps: int = 250):
        """
        Complete project flow: Initializes project, then runs execution cycle.
        HITL will only occur after root node planning, not immediately after initialization.
        This is intended to be the primary entry point for running a project.
        """
        logger.info(f"ExecutionEngine: Starting project flow with root goal: '{root_goal}'")
        root_node = self.project_initializer.initialize_project(
            root_goal=root_goal,
            task_graph=self.task_graph,
            knowledge_store=self.knowledge_store,
            root_task_type=root_task_type
        )
        
        if not root_node: # Should not happen if initialize_project raises on critical failure
            logger.error("ExecutionEngine: Root node not created by initializer. Cannot proceed.")
            return None

        # REMOVED: The unwanted HITL call after initialization
        # await self.hitl_coordinator.review_initial_project_goal(...)
        
        logger.info("ExecutionEngine: Project initialized. Proceeding directly to execution cycle.")
        # Use timeout from config
        node_timeout = self.config.execution.node_execution_timeout_seconds
        return await self.run_cycle(max_steps, node_timeout_seconds=node_timeout)

    async def run_cycle(self, max_steps: Optional[int] = None, node_timeout_seconds: float = 600.0):
        """
        Runs the execution loop for a specified number of steps or until completion/deadlock.
        
        Args:
            max_steps: Maximum number of execution steps
            node_timeout_seconds: Maximum time in seconds for overall execution (default: 600 = 10 minutes)
        """
        # Use config default if max_steps not provided
        max_steps = max_steps or self.config.execution.max_execution_steps
        
        # Track start time for timeout
        start_time = time.time()
        
        logger.info(f"\n--- Starting Execution Cycle (max_steps: {max_steps}, timeout: {node_timeout_seconds}s) ---")
        
        root_node_initial_check = self.task_graph.get_node("root")
        if not self.task_graph.root_graph_id or not root_node_initial_check:
            logger.error("ExecutionEngine: Project not initialized properly or root node missing before cycle start.")
            return {"error": "Project initialization failed - root node missing"}
        if root_node_initial_check.status in [TaskStatus.CANCELLED, TaskStatus.FAILED]:
            logger.warning(f"ExecutionEngine: Root node is already {root_node_initial_check.status.name}. Cycle may not run effectively.")
            self._log_final_statuses()
            # Return error if root node failed
            if root_node_initial_check.status == TaskStatus.FAILED:
                return {"error": f"Root node failed: {root_node_initial_check.error or 'Unknown error'}"}
            return root_node_initial_check.result

        for step in range(max_steps):
            # Check for timeout
            elapsed_time = time.time() - start_time
            if elapsed_time > node_timeout_seconds:
                logger.error(f"\n--- Execution Timeout: Exceeded {node_timeout_seconds}s timeout after {elapsed_time:.2f}s ---")
                # Mark root node as failed with timeout error
                root_node = self.task_graph.get_node("root")
                if root_node:
                    root_node.update_status(TaskStatus.FAILED, error_msg=f"Execution timeout after {elapsed_time:.2f}s")
                self._log_final_statuses()
                return {"error": f"Execution timeout: Exceeded {node_timeout_seconds}s limit"}
            
            logger.info(f"\n--- Execution Step {step + 1} of {max_steps} (elapsed: {elapsed_time:.2f}s) ---")
            
            # Delegate step execution to CycleManager
            # Pass the update callback from node processor if available
            update_callback = None
            if hasattr(self.node_processor, 'update_callback') and self.node_processor.update_callback:
                update_callback = self.node_processor.update_callback
            
            try:
                processed_in_step = await self.cycle_manager.execute_step(
                    task_graph=self.task_graph,
                    state_manager=self.state_manager,
                    node_processor=self.node_processor, # type: ignore
                    knowledge_store=self.knowledge_store,
                    update_callback=update_callback
                )
            except Exception as e:
                logger.error(f"\n--- Execution Error: {str(e)} ---")
                # Mark root node as failed with error
                root_node = self.task_graph.get_node("root")
                if root_node:
                    root_node.update_status(TaskStatus.FAILED, error_msg=f"Execution error: {str(e)}")
                self._log_final_statuses()
                return {"error": f"Execution failed: {str(e)}"}
            
            # --- Check for completion or deadlock for this step ---
            active_statuses = {TaskStatus.PENDING, TaskStatus.READY, TaskStatus.RUNNING, TaskStatus.PLAN_DONE, TaskStatus.AGGREGATING, TaskStatus.NEEDS_REPLAN}
            all_nodes_after_step = self.task_graph.get_all_nodes() 

            # Check for critical failures (e.g., all nodes failed)
            failed_nodes = [n for n in all_nodes_after_step if n.status == TaskStatus.FAILED]
            if failed_nodes:
                # Check if any critical nodes failed (e.g., root or key execution nodes)
                critical_failures = [n for n in failed_nodes if n.layer == 0 or "execution" in n.task_id.lower()]
                if critical_failures:
                    logger.error(f"\n--- Execution Failed: Critical node failures detected ---")
                    for node in critical_failures:
                        logger.error(f"    - Failed: {node.task_id}, Error: {node.error}")
                    self._log_final_statuses()
                    # Return the most relevant error
                    primary_error = critical_failures[0].error or "Critical node failure"
                    return {"error": f"Execution failed: {primary_error}"}

            if not any(n.status in active_statuses for n in all_nodes_after_step):
                logger.success("\n--- Execution Finished: No active nodes left. ---")
                break

            if not processed_in_step and any(n.status in active_statuses for n in all_nodes_after_step):
                logger.warning("\n--- No progress made in this step. Checking for stuck nodes... ---")
                
                # Try to recover stuck nodes before declaring deadlock
                active_nodes = [n for n in all_nodes_after_step if n.status in active_statuses]
                
                # CRITICAL PREEMPTIVE FIX: Check for single hanging RUNNING node
                single_running_fix = await self._check_single_running_hang(active_nodes)
                if single_running_fix:
                    logger.info(f"Applied immediate fix for hanging RUNNING node: {single_running_fix}")
                    continue  # Skip deadlock check and continue with next step
                
                # CRITICAL PREEMPTIVE FIX: Check for parent-child sync failure
                immediate_fix = await self._check_parent_child_sync_failure(active_nodes)
                if immediate_fix:
                    logger.info(f"Applied immediate fix for parent-child sync: {immediate_fix}")
                    continue  # Skip deadlock check and continue with next step
                
                recovery_attempted = await self._check_and_recover_stuck_nodes(active_nodes, time.time())
                
                if recovery_attempted:
                    logger.info("Recovery actions taken for stuck nodes. Continuing execution...")
                    continue  # Skip deadlock check and continue with next step
                
                logger.error("\n--- Execution Halted: No progress made and no recovery possible. Deadlock detected. ---")
                
                # Detailed deadlock diagnostics
                deadlock_info = self._diagnose_deadlock(all_nodes_after_step, active_statuses)
                
                for n_active in all_nodes_after_step:
                    if n_active.status in active_statuses:
                        logger.error(f"    - Active: {n_active.task_id}, Status: {n_active.status.name}, Goal: '{n_active.goal[:50]}...'")
                        
                        # Log why each node is stuck
                        if n_active.status == TaskStatus.PENDING:
                            if n_active.parent_node_id:
                                parent = self.task_graph.get_node(n_active.parent_node_id)
                                if parent:
                                    logger.error(f"      -> Waiting for parent {parent.task_id} (status: {parent.status.name})")
                            container_graph = self.state_manager._find_container_graph_id_for_node(n_active)
                            if container_graph:
                                preds = self.task_graph.get_node_predecessors(container_graph, n_active.task_id)
                                if preds:
                                    logger.error(f"      -> Waiting for predecessors: {[f'{p.task_id}({p.status.name})' for p in preds]}")
                        
                        elif n_active.status == TaskStatus.PLAN_DONE:
                            if n_active.sub_graph_id:
                                sub_nodes = self.task_graph.get_nodes_in_graph(n_active.sub_graph_id)
                                incomplete = [n for n in sub_nodes if not is_terminal_status(n.status)]
                                if incomplete:
                                    logger.error(f"      -> Waiting for {len(incomplete)} sub-tasks to complete")
                                    for inc in incomplete[:3]:  # Show first 3
                                        logger.error(f"         - {inc.task_id}: {inc.status.name}")
                
                self._log_final_statuses()
                return {"error": f"Execution deadlock: {deadlock_info}"}
        
        if step == max_steps - 1: # type: ignore # Check if loop completed due to max_steps
             # Check active nodes one last time if loop finished due to max_steps
            if any(n.status in active_statuses for n in self.task_graph.get_all_nodes()): # type: ignore
                 logger.warning("\n--- Execution Finished: Reached max steps with active nodes remaining. ---")
                 return {"error": f"Execution incomplete: Reached max steps ({max_steps}) with active nodes remaining"}

        self._log_final_statuses()
        
        root_node_final = self.task_graph.get_node("root")
        
        # Check if root node failed
        if root_node_final and root_node_final.status == TaskStatus.FAILED:
            return {"error": f"Task failed: {root_node_final.error or 'Unknown error'}"}
        
        # Check if execution completed successfully
        if root_node_final and root_node_final.status == TaskStatus.DONE:
            # Return the result even if it's None or empty
            # An empty result from a successful execution is valid
            if root_node_final.result is not None:
                return root_node_final.result
            else:
                # Check if we have a meaningful summary that indicates success
                if root_node_final.output_summary and "completed" in root_node_final.output_summary.lower():
                    # Return a success indicator with the summary
                    return {"status": "success", "summary": root_node_final.output_summary}
                else:
                    # Return empty dict to indicate successful completion with no output
                    return {}
        
        # If we get here, something went wrong
        if root_node_final:
            return {"error": f"Execution did not complete successfully. Final status: {root_node_final.status.name}"}
        else:
            return {"error": "No root node found"}

    async def _check_and_recover_stuck_nodes(self, active_nodes, current_time: float) -> bool:
        """
        Check for nodes that have been stuck in the same state for too long
        and attempt recovery actions.
        
        Returns:
            bool: True if any recovery action was taken
        """
        recovered = False
        
        # Get timeout thresholds from config
        timeout_config = getattr(self.config.execution, 'timeout_strategy', None)
        if timeout_config:
            warning_threshold = timeout_config.warning_threshold_seconds
            soft_timeout = timeout_config.soft_timeout_seconds
            hard_timeout = timeout_config.hard_timeout_seconds
            max_attempts = timeout_config.max_recovery_attempts
            aggressive_recovery = timeout_config.enable_aggressive_recovery
        else:
            # Fallback to original logic
            node_timeout = self.config.execution.node_execution_timeout_seconds / 3
            warning_threshold = node_timeout * 0.5
            soft_timeout = node_timeout
            hard_timeout = self.config.execution.node_execution_timeout_seconds
            max_attempts = 2
            aggressive_recovery = False
        
        for node in active_nodes:
            # Track when we first see this node in its current status
            node_key = f"{node.task_id}_{node.status.name}"
            if node_key not in self.node_start_times:
                self.node_start_times[node_key] = current_time
                continue
            
            # Check if node has been stuck too long
            time_in_status = current_time - self.node_start_times[node_key]
            
            # Escalating timeout strategy
            recovery_level = None
            if time_in_status > hard_timeout:
                recovery_level = "HARD"
            elif time_in_status > soft_timeout:
                recovery_level = "SOFT"
            elif time_in_status > warning_threshold:
                recovery_level = "WARNING"
            
            if recovery_level:
                if recovery_level == "WARNING":
                    logger.warning(f"Node {node.task_id} approaching timeout: {time_in_status:.0f}s in {node.status.name}")
                    continue  # Just warn, don't take action yet
                
                logger.warning(f"Node {node.task_id} timeout ({recovery_level}): {time_in_status:.0f}s in {node.status.name}")
                
                # Track recovery attempts
                if node.task_id not in self.stuck_node_attempts:
                    self.stuck_node_attempts[node.task_id] = 0
                
                if self.stuck_node_attempts[node.task_id] < max_attempts:
                    self.stuck_node_attempts[node.task_id] += 1
                    
                    # Try hierarchy-aware recovery with escalation level
                    recovery_action = await self._attempt_hierarchical_recovery(
                        node, time_in_status, recovery_level, aggressive_recovery
                    )
                    if recovery_action:
                        logger.warning(f"Recovery action for {node.task_id}: {recovery_action}")
                        recovered = True
                    else:
                        # Fallback to original recovery strategies
                        if node.status == TaskStatus.RUNNING:
                            # Mark as NEEDS_REPLAN to retry
                            logger.warning(f"Marking stuck RUNNING node {node.task_id} as NEEDS_REPLAN")
                            node.update_status(TaskStatus.NEEDS_REPLAN, 
                                             error_msg=f"Node stuck in RUNNING state for {time_in_status:.0f}s")
                            self.knowledge_store.add_or_update_record_from_node(node)
                            recovered = True
                        
                        elif node.status == TaskStatus.PLAN_DONE:
                            # Force aggregation check
                            if self.state_manager.can_aggregate(node):
                                logger.warning(f"Force transitioning stuck PLAN_DONE node {node.task_id} to AGGREGATING")
                                node.update_status(TaskStatus.AGGREGATING)
                                self.knowledge_store.add_or_update_record_from_node(node)
                                recovered = True
                else:
                    # Max attempts reached, fail the node
                    logger.error(f"Node {node.task_id} recovery failed after {self.stuck_node_attempts[node.task_id]} attempts")
                    node.update_status(TaskStatus.FAILED, 
                                     error_msg=f"Node stuck in {node.status.name} for {time_in_status:.0f}s, recovery failed")
                    self.knowledge_store.add_or_update_record_from_node(node)
                    recovered = True
        
        return recovered

    async def _check_single_running_hang(self, active_nodes) -> str:
        """
        Check for a single RUNNING node that appears to be hanging.
        This is often caused by executor adapters getting stuck.
        
        Returns:
            str: Description of fix applied, or empty string if no fix needed
        """
        # Check if we have exactly one active node and it's RUNNING
        if len(active_nodes) == 1 and active_nodes[0].status == TaskStatus.RUNNING:
            hanging_node = active_nodes[0]
            
            # Check how long it's been running
            node_key = f"{hanging_node.task_id}_{hanging_node.status.name}"
            if node_key in self.node_start_times:
                time_in_status = time.time() - self.node_start_times[node_key]
                
                # Apply aggressive timeout for single hanging nodes (90 seconds)
                if time_in_status > 90:
                    logger.warning(f"EMERGENCY: Single RUNNING node {hanging_node.task_id} hanging for {time_in_status:.0f}s - forcing recovery")
                    
                    # Force the node to retry
                    hanging_node.update_status(TaskStatus.NEEDS_REPLAN, 
                                             error_msg=f"Emergency recovery: Node hung in RUNNING for {time_in_status:.0f}s")
                    self.knowledge_store.add_or_update_record_from_node(hanging_node)
                    
                    return f"Emergency: Forced hanging RUNNING node {hanging_node.task_id[:8]} to NEEDS_REPLAN after {time_in_status:.0f}s"
        
        return ""

    async def _check_parent_child_sync_failure(self, active_nodes) -> str:
        """
        Check for the specific pattern where a RUNNING parent has PENDING children
        that can't find their container graph. Apply immediate fix.
        
        Returns:
            str: Description of fix applied, or empty string if no fix needed
        """
        # Find RUNNING nodes with PENDING children
        running_nodes = [n for n in active_nodes if n.status == TaskStatus.RUNNING]
        pending_nodes = [n for n in active_nodes if n.status == TaskStatus.PENDING]
        
        for running_parent in running_nodes:
            # Find children of this parent
            children = [n for n in pending_nodes if n.parent_node_id == running_parent.task_id]
            
            if children:
                # Check if children can't find their container graph
                container_issues = []
                for child in children:
                    container_graph_id = self.state_manager._find_container_graph_id_for_node(child)
                    if not container_graph_id:
                        container_issues.append(child)
                
                if container_issues:
                    logger.warning(f"CRITICAL FIX: Parent {running_parent.task_id} has {len(container_issues)} children with container graph issues")
                    
                    # Find the graph containing the children
                    children_graph_id = None
                    for graph_id, graph_obj in self.task_graph.graphs.items():
                        if any(child.task_id in graph_obj.nodes for child in children):
                            children_graph_id = graph_id
                            break
                    
                    if children_graph_id:
                        # Set sub_graph_id on parent if not set
                        if not running_parent.sub_graph_id:
                            running_parent.sub_graph_id = children_graph_id
                            logger.info(f"Set sub_graph_id {children_graph_id} on parent {running_parent.task_id}")
                        
                        # Force transition to PLAN_DONE
                        running_parent.update_status(TaskStatus.PLAN_DONE, 
                                                   result_summary=f"Emergency transition: had {len(children)} waiting children")
                        self.knowledge_store.add_or_update_record_from_node(running_parent)
                        
                        return f"Emergency fix: Transitioned parent {running_parent.task_id[:8]} RUNNING->PLAN_DONE for {len(children)} stuck children"
                    else:
                        logger.error(f"Could not find graph containing children of {running_parent.task_id}")
        
        return ""

    async def _attempt_hierarchical_recovery(self, node: TaskNode, time_in_status: float, 
                                             recovery_level: str = "SOFT", aggressive: bool = False) -> str:
        """
        Attempt hierarchy-aware recovery strategies based on parent-child relationships.
        
        Args:
            node: The stuck node to recover
            time_in_status: How long the node has been in current status
            recovery_level: "SOFT" or "HARD" indicating escalation level
            aggressive: Whether to use aggressive recovery strategies
            
        Returns:
            str: Description of recovery action taken, or empty string if no action
        """
        
        # Strategy 1: PENDING nodes with parent issues
        if node.status == TaskStatus.PENDING:
            if node.parent_node_id:
                parent = self.task_graph.get_node(node.parent_node_id)
                if parent:
                    # Parent stuck in RUNNING - escalated intervention
                    if parent.status == TaskStatus.RUNNING:
                        # Check if parent has been running too long
                        parent_key = f"{parent.task_id}_{parent.status.name}"
                        if parent_key in self.node_start_times:
                            parent_time = time.time() - self.node_start_times[parent_key]
                            
                            # Escalated recovery based on level
                            if recovery_level == "HARD" or (aggressive and parent_time > 300):
                                logger.warning(f"HARD recovery: Forcing completion of stuck parent {parent.task_id}")
                                parent.update_status(TaskStatus.NEEDS_REPLAN, 
                                                   error_msg=f"Parent stuck in RUNNING for {parent_time:.0f}s (HARD timeout)")
                                self.knowledge_store.add_or_update_record_from_node(parent)
                                return f"HARD: Forced parent {parent.task_id[:8]} to NEEDS_REPLAN"
                            elif recovery_level == "SOFT" and parent_time > 600:
                                logger.warning(f"SOFT recovery: Nudging stuck parent {parent.task_id}")
                                parent.update_status(TaskStatus.NEEDS_REPLAN, 
                                                   error_msg=f"Parent stuck in RUNNING for {parent_time:.0f}s (SOFT timeout)")
                                self.knowledge_store.add_or_update_record_from_node(parent)
                                return f"SOFT: Forced parent {parent.task_id[:8]} to NEEDS_REPLAN"
                    
                    # Parent has wrong status for children to proceed
                    elif parent.status not in (TaskStatus.RUNNING, TaskStatus.PLAN_DONE, TaskStatus.DONE):
                        logger.warning(f"Parent {parent.task_id} has invalid status {parent.status.name} for child")
                        # Try to force parent to appropriate status if possible
                        if self.state_manager._check_parent_conditions_for_ready(node):
                            node.update_status(TaskStatus.READY)
                            self.knowledge_store.add_or_update_record_from_node(node)
                            return f"Bypassed invalid parent status, promoted to READY"
            
            # No parent - check predecessors
            else:
                container_graph = self.state_manager._find_container_graph_id_for_node(node)
                if container_graph:
                    preds = self.task_graph.get_node_predecessors(container_graph, node.task_id)
                    if preds:
                        stuck_preds = [p for p in preds if p.status in [TaskStatus.RUNNING, TaskStatus.PENDING]]
                        if stuck_preds and self.state_manager._check_parent_conditions_for_ready(node):
                            # Force transition if predecessors are taking too long
                            node.update_status(TaskStatus.READY)
                            self.knowledge_store.add_or_update_record_from_node(node)
                            return f"Bypassed {len(stuck_preds)} stuck predecessors"
        
        # Strategy 2: RUNNING nodes stuck in execution
        elif node.status == TaskStatus.RUNNING:
            # CRITICAL: Check for single RUNNING node hanging (likely executor adapter issue)
            all_active_nodes = [n for n in self.task_graph.get_all_nodes() if n.status in [TaskStatus.PENDING, TaskStatus.READY, TaskStatus.RUNNING, TaskStatus.PLAN_DONE, TaskStatus.AGGREGATING, TaskStatus.NEEDS_REPLAN]]
            single_running_hang = (len(all_active_nodes) == 1 and all_active_nodes[0].task_id == node.task_id)
            
            if single_running_hang and (recovery_level == "HARD" or time_in_status > 120):  # 2 minute timeout for single hanging nodes
                logger.warning(f"CRITICAL: Single RUNNING node {node.task_id} hanging for {time_in_status:.0f}s - likely executor adapter stuck")
                node.update_status(TaskStatus.NEEDS_REPLAN, 
                                 error_msg=f"Node stuck in RUNNING for {time_in_status:.0f}s - executor likely hanging")
                self.knowledge_store.add_or_update_record_from_node(node)
                return f"CRITICAL: Single hanging RUNNING node {node.task_id[:8]} forced to NEEDS_REPLAN"
            
            # Check if this node should have created subtasks but hasn't
            elif not node.sub_graph_id and node.node_type == NodeType.PLAN:
                # This PLAN node is stuck in RUNNING without creating subtasks
                node.update_status(TaskStatus.NEEDS_REPLAN, 
                                 error_msg=f"PLAN node stuck in RUNNING without creating subtasks")
                self.knowledge_store.add_or_update_record_from_node(node)
                return "PLAN node stuck without subtasks, forcing replan"
            
            # CRITICAL FIX: Check if this RUNNING node has children that can't find their container graph
            all_nodes = self.task_graph.get_all_nodes()
            stuck_children = [n for n in all_nodes if n.parent_node_id == node.task_id and n.status == TaskStatus.PENDING]
            
            if stuck_children and (recovery_level == "HARD" or time_in_status > 60):  # 1 minute timeout
                # Force parent to PLAN_DONE so children can proceed
                logger.warning(f"CRITICAL: Parent {node.task_id} stuck RUNNING with {len(stuck_children)} PENDING children")
                
                # Find or create sub_graph_id for the children
                children_graph_id = None
                for graph_id, graph_obj in self.task_graph.graphs.items():
                    if any(child.task_id in graph_obj.nodes for child in stuck_children):
                        children_graph_id = graph_id
                        break
                
                if children_graph_id:
                    # Set the sub_graph_id on the parent
                    node.sub_graph_id = children_graph_id
                    # Force transition to PLAN_DONE
                    node.update_status(TaskStatus.PLAN_DONE, 
                                     result_summary=f"Forced transition: had {len(stuck_children)} waiting children")
                    self.knowledge_store.add_or_update_record_from_node(node)
                    return f"CRITICAL: Forced RUNNING parent {node.task_id[:8]} to PLAN_DONE for {len(stuck_children)} children"
                else:
                    logger.error(f"Could not find graph containing children of {node.task_id}")
                    return f"Failed to find children graph for {node.task_id[:8]}"
        
        # Strategy 3: PLAN_DONE nodes with stuck children
        elif node.status == TaskStatus.PLAN_DONE and node.sub_graph_id:
            sub_nodes = self.task_graph.get_nodes_in_graph(node.sub_graph_id)
            stuck_children = [n for n in sub_nodes if n.status in [TaskStatus.PENDING, TaskStatus.RUNNING]]
            
            if stuck_children:
                # Try to unstick the most problematic children
                for child in stuck_children[:2]:  # Limit to first 2
                    child_recovery = await self._attempt_hierarchical_recovery(
                        child, time_in_status, recovery_level, aggressive
                    )
                    if child_recovery:
                        return f"Fixed child {child.task_id[:8]}: {child_recovery}"
                
                # If children can't be fixed, force aggregation with partial results
                if len(stuck_children) < len(sub_nodes) / 2:  # Less than half stuck
                    logger.warning(f"Forcing aggregation with {len(stuck_children)} stuck children")
                    node.update_status(TaskStatus.AGGREGATING)
                    self.knowledge_store.add_or_update_record_from_node(node)
                    return f"Forced aggregation ignoring {len(stuck_children)} stuck children"
        
        return ""  # No recovery action taken

    def _validate_execution_state(self, all_nodes) -> List[str]:
        """
        Validate the overall execution state for inconsistencies.
        
        Returns:
            List of validation errors found
        """
        errors = []
        
        # Check for invalid parent-child combinations
        for node in all_nodes:
            if node.parent_node_id:
                parent = self.task_graph.get_node(node.parent_node_id)
                if parent:
                    # Child can't be READY/RUNNING if parent is not RUNNING/PLAN_DONE
                    if node.status in [TaskStatus.READY, TaskStatus.RUNNING]:
                        if parent.status not in [TaskStatus.RUNNING, TaskStatus.PLAN_DONE, TaskStatus.DONE]:
                            errors.append(f"Invalid state: Child {node.task_id[:8]} is {node.status.name} but parent {parent.task_id[:8]} is {parent.status.name}")
                    
                    # PLAN_DONE parent should have active children or be done
                    if parent.status == TaskStatus.PLAN_DONE and parent.sub_graph_id:
                        children = self.task_graph.get_nodes_in_graph(parent.sub_graph_id)
                        if children and all(child.status in [TaskStatus.DONE, TaskStatus.FAILED] for child in children):
                            # All children done but parent still PLAN_DONE
                            if parent not in [n for n in all_nodes if n.status == TaskStatus.AGGREGATING]:
                                errors.append(f"Invalid state: Parent {parent.task_id[:8]} PLAN_DONE with all children complete")
        
        # Check for nodes with invalid sub-graph relationships
        for node in all_nodes:
            if node.sub_graph_id:
                sub_nodes = self.task_graph.get_nodes_in_graph(node.sub_graph_id)
                if not sub_nodes and node.status == TaskStatus.PLAN_DONE:
                    errors.append(f"Invalid state: Node {node.task_id[:8]} PLAN_DONE with empty sub-graph")
        
        # Check for circular parent relationships
        visited_chains = set()
        for node in all_nodes:
            if node.parent_node_id and node.task_id not in visited_chains:
                chain = []
                current = node
                while current and len(chain) < 10:  # Prevent infinite loops
                    if current.task_id in chain:
                        errors.append(f"Circular parent relationship detected: {' -> '.join(chain + [current.task_id[:8]])}")
                        break
                    chain.append(current.task_id)
                    visited_chains.add(current.task_id)
                    if current.parent_node_id:
                        current = self.task_graph.get_node(current.parent_node_id)
                    else:
                        break
        
        return errors

    def _diagnose_deadlock(self, all_nodes, active_statuses) -> str:
        """Diagnose the cause of deadlock with comprehensive hierarchical analysis."""
        active_nodes = [n for n in all_nodes if n.status in active_statuses]
        
        # Count nodes by status
        status_counts = {}
        for node in active_nodes:
            status_counts[node.status.name] = status_counts.get(node.status.name, 0) + 1
        
        # Enhanced deadlock pattern analysis
        deadlock_patterns = self._analyze_deadlock_patterns(active_nodes)
        dependency_chains = self._build_dependency_visualization(active_nodes)
        validation_errors = self._validate_execution_state(all_nodes)
        
        # Log comprehensive diagnostics
        logger.error("=== DEADLOCK ANALYSIS ===")
        logger.error(f"Active nodes: {len(active_nodes)} ({', '.join(f'{k}:{v}' for k,v in status_counts.items())})")
        
        if validation_errors:
            logger.error("State validation errors:")
            for error in validation_errors:
                logger.error(f"  - {error}")
        
        if deadlock_patterns:
            logger.error("Detected patterns:")
            for pattern in deadlock_patterns:
                logger.error(f"  - {pattern}")
        
        if dependency_chains:
            logger.error("Dependency chains:")
            for chain in dependency_chains:
                logger.error(f"  {chain}")
        
        # Build concise message for return
        primary_pattern = deadlock_patterns[0] if deadlock_patterns else "Unknown deadlock pattern"
        return f"No progress possible. {len(active_nodes)} nodes stuck ({', '.join(f'{k}:{v}' for k,v in status_counts.items())}). Pattern: {primary_pattern}"

    def _analyze_deadlock_patterns(self, active_nodes) -> List[str]:
        """Analyze common deadlock patterns in the active nodes."""
        patterns = []
        
        # Group nodes by status
        nodes_by_status = {}
        for node in active_nodes:
            status = node.status.name
            if status not in nodes_by_status:
                nodes_by_status[status] = []
            nodes_by_status[status].append(node)
        
        # Pattern 1: Single RUNNING node stuck (executor hanging)
        running_nodes = nodes_by_status.get('RUNNING', [])
        if len(running_nodes) == 1 and len(active_nodes) == 1:
            running_node = running_nodes[0]
            patterns.append(f"Single Node Execution Hang: Node {running_node.task_id[:8]} stuck in RUNNING (likely executor adapter hanging)")
        
        # Pattern 2: Parent-Child Synchronization Failure
        pending_nodes = nodes_by_status.get('PENDING', [])
        
        if running_nodes and pending_nodes:
            # Check if pending nodes are children of running nodes
            running_ids = {node.task_id for node in running_nodes}
            children_of_running = [
                node for node in pending_nodes 
                if node.parent_node_id in running_ids
            ]
            if children_of_running:
                patterns.append(f"Parent-Child Sync Failure: {len(running_nodes)} parent(s) stuck RUNNING, {len(children_of_running)} children stuck PENDING")
        
        # Pattern 3: PLAN_DONE nodes with incomplete sub-tasks
        plan_done_nodes = nodes_by_status.get('PLAN_DONE', [])
        if plan_done_nodes:
            for node in plan_done_nodes:
                if node.sub_graph_id:
                    sub_nodes = self.task_graph.get_nodes_in_graph(node.sub_graph_id)
                    incomplete_sub_nodes = [n for n in sub_nodes if n.status in [TaskStatus.PENDING, TaskStatus.READY, TaskStatus.RUNNING]]
                    if incomplete_sub_nodes:
                        patterns.append(f"Stuck Aggregation: Node {node.task_id[:8]} waiting for {len(incomplete_sub_nodes)} sub-tasks")
        
        # Pattern 4: Circular dependencies
        for node in pending_nodes:
            if self._has_circular_dependency(node, visited=set()):
                patterns.append(f"Circular Dependency: Node {node.task_id[:8]} in dependency cycle")
                break  # Only report one to avoid spam
        
        # Pattern 5: Orphaned nodes (PENDING without proper parent status)
        orphaned = []
        for node in pending_nodes:
            if node.parent_node_id:
                parent = self.task_graph.get_node(node.parent_node_id)
                if parent and parent.status not in (TaskStatus.RUNNING, TaskStatus.PLAN_DONE, TaskStatus.DONE):
                    orphaned.append(node)
        
        if orphaned:
            patterns.append(f"Orphaned Nodes: {len(orphaned)} PENDING nodes with invalid parent status")
        
        return patterns
    
    def _build_dependency_visualization(self, active_nodes) -> List[str]:
        """Build visual representation of dependency chains for stuck nodes."""
        chains = []
        
        # Build parent-child chains
        for node in active_nodes:
            if node.status == TaskStatus.PENDING and node.parent_node_id:
                chain = self._build_dependency_chain(node)
                if chain:
                    chains.append(chain)
        
        # Build predecessor chains for first few nodes
        for node in active_nodes[:3]:  # Limit to prevent spam
            container_graph = self.state_manager._find_container_graph_id_for_node(node)
            if container_graph:
                preds = self.task_graph.get_node_predecessors(container_graph, node.task_id)
                if preds:
                    pred_chain = " -> ".join([f"{p.task_id[:8]}({p.status.name})" for p in preds])
                    chains.append(f"Predecessors: {pred_chain} -> {node.task_id[:8]}({node.status.name})")
        
        return chains[:10]  # Limit output
    
    def _build_dependency_chain(self, node, max_depth=5) -> str:
        """Build a dependency chain string showing parent hierarchy."""
        chain_parts = []
        current = node
        depth = 0
        
        while current and depth < max_depth:
            chain_parts.append(f"{current.task_id[:8]}({current.status.name})")
            if current.parent_node_id:
                current = self.task_graph.get_node(current.parent_node_id)
                depth += 1
            else:
                break
        
        if len(chain_parts) > 1:
            chain_parts.reverse()
            return "Parent chain: " + " -> ".join(chain_parts)
        return ""
    
    def _has_circular_dependency(self, node, visited=None, max_depth=10) -> bool:
        """Check if a node has circular dependencies in its parent chain."""
        if visited is None:
            visited = set()
        
        if len(visited) > max_depth or node.task_id in visited:
            return True
        
        visited.add(node.task_id)
        
        if node.parent_node_id:
            parent = self.task_graph.get_node(node.parent_node_id)
            if parent:
                return self._has_circular_dependency(parent, visited.copy(), max_depth)
        
        return False

    def _log_final_statuses(self):
        logger.info("\n--- Final Node Statuses & Results ---")
        all_final_nodes = sorted(self.task_graph.get_all_nodes(), key=lambda n: (n.layer, n.task_id)) # type: ignore
        for node in all_final_nodes:
            status_str = node.status.name if isinstance(node.status, TaskStatus) else str(node.status) # type: ignore
            result_summary = ""
            if node.result is not None: # type: ignore
                if isinstance(node.result, (dict, list)):  # type: ignore
                    try:
                        result_summary = pprint.pformat(node.result) # type: ignore
                        if len(result_summary) > 150:
                             result_summary = result_summary[:150] + "..."
                    except Exception:
                        result_summary = str(node.result)[:150] + "..." if len(str(node.result)) > 150 else str(node.result) # type: ignore
                else:
                    result_summary = str(node.result)[:150] + "..." if len(str(node.result)) > 150 else str(node.result) # type: ignore
            
            error_info = f", Error: {node.error}" if node.error else "" # type: ignore
            output_s = f", OutputSummary: {node.output_summary}" if node.output_summary else "" # type: ignore

            logger.info(f"  Node: {node.task_id:<15} Layer: {node.layer} Status: {status_str:<12} Goal: '{node.goal[:40]:<40}...' Result: {result_summary:<50}{output_s}{error_info}") # type: ignore
