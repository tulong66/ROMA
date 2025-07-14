from loguru import logger
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskStatus, NodeType, TaskType
from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import KnowledgeStore # For logging to KS
from sentientresearchagent.hierarchical_agent_framework.utils.hitl_utils import request_human_review
from sentientresearchagent.hierarchical_agent_framework.types import is_terminal_status

from typing import TYPE_CHECKING
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
        
        # Return result or error message
        if root_node_final and root_node_final.result:
            return root_node_final.result
        else:
            return {"error": "No result generated"}

    async def _check_and_recover_stuck_nodes(self, active_nodes, current_time: float) -> bool:
        """
        Check for nodes that have been stuck in the same state for too long
        and attempt recovery actions.
        
        Returns:
            bool: True if any recovery action was taken
        """
        recovered = False
        node_timeout = self.config.execution.node_execution_timeout_seconds / 3  # Per-node timeout is 1/3 of total
        
        for node in active_nodes:
            # Track when we first see this node in its current status
            node_key = f"{node.task_id}_{node.status.name}"
            if node_key not in self.node_start_times:
                self.node_start_times[node_key] = current_time
                continue
            
            # Check if node has been stuck too long
            time_in_status = current_time - self.node_start_times[node_key]
            
            if time_in_status > node_timeout:
                logger.warning(f"Node {node.task_id} has been in {node.status.name} for {time_in_status:.0f}s")
                
                # Track recovery attempts
                if node.task_id not in self.stuck_node_attempts:
                    self.stuck_node_attempts[node.task_id] = 0
                
                if self.stuck_node_attempts[node.task_id] < 2:  # Max 2 recovery attempts
                    self.stuck_node_attempts[node.task_id] += 1
                    
                    # Different recovery strategies based on status
                    if node.status == TaskStatus.PENDING:
                        # Force transition to READY if parent conditions met
                        if self.state_manager._check_parent_conditions_for_ready(node):
                            logger.warning(f"Force transitioning stuck PENDING node {node.task_id} to READY")
                            node.update_status(TaskStatus.READY)
                            self.knowledge_store.add_or_update_record_from_node(node)
                            recovered = True
                    
                    elif node.status == TaskStatus.RUNNING:
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

    def _diagnose_deadlock(self, all_nodes, active_statuses) -> str:
        """Diagnose the cause of deadlock and return a descriptive message."""
        active_nodes = [n for n in all_nodes if n.status in active_statuses]
        
        # Count nodes by status
        status_counts = {}
        for node in active_nodes:
            status_counts[node.status.name] = status_counts.get(node.status.name, 0) + 1
        
        # Common deadlock scenarios
        pending_nodes = [n for n in active_nodes if n.status == TaskStatus.PENDING]
        plan_done_nodes = [n for n in active_nodes if n.status == TaskStatus.PLAN_DONE]
        
        deadlock_reasons = []
        
        # Check for circular dependencies
        if pending_nodes:
            for node in pending_nodes:
                if node.parent_node_id:
                    parent = self.task_graph.get_node(node.parent_node_id)
                    if parent and parent.status not in (TaskStatus.RUNNING, TaskStatus.PLAN_DONE):
                        deadlock_reasons.append(f"Node {node.task_id} waiting for parent {parent.task_id} with incompatible status {parent.status.name}")
        
        # Check for stuck PLAN_DONE nodes
        if plan_done_nodes:
            for node in plan_done_nodes:
                if node.sub_graph_id:
                    sub_nodes = self.task_graph.get_nodes_in_graph(node.sub_graph_id)
                    stuck_sub_nodes = [n for n in sub_nodes if n.status in active_statuses and n.status != TaskStatus.DONE]
                    if stuck_sub_nodes:
                        deadlock_reasons.append(f"Node {node.task_id} has {len(stuck_sub_nodes)} incomplete sub-tasks")
        
        # Build diagnostic message
        if deadlock_reasons:
            return f"No progress possible. {len(active_nodes)} nodes stuck ({', '.join(f'{k}:{v}' for k,v in status_counts.items())}). Root causes: {'; '.join(deadlock_reasons[:2])}"
        else:
            return f"No progress possible. {len(active_nodes)} nodes stuck ({', '.join(f'{k}:{v}' for k,v in status_counts.items())}). Check logs for details."

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
