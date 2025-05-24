from loguru import logger
from sentientresearchagent.hierarchical_agent_framework.graph.task_graph import TaskGraph
# NodeProcessor will be defined later, so we use a forward reference or Any for now
# from sentientresearchagent.hierarchical_agent_framework.node.node_processor import NodeProcessor
from typing import Any as NodeProcessorType # Placeholder for NodeProcessor
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskStatus, NodeType, TaskType
from sentientresearchagent.hierarchical_agent_framework.graph.state_manager import StateManager
from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import KnowledgeStore # For logging to KS
from sentientresearchagent.hierarchical_agent_framework.utils.hitl_utils import request_human_review

# Ensure NodeProcessor is imported for specific type hinting
from sentientresearchagent.hierarchical_agent_framework.node.node_processor import NodeProcessor


from agno.exceptions import StopAgentRun # Added import
from typing import Optional, Callable
import pprint # For logging results
import asyncio # Import asyncio

# Import new ProjectInitializer
from .project_initializer import ProjectInitializer

# Import HITLCoordinator
from sentientresearchagent.hierarchical_agent_framework.node.hitl_coordinator import HITLCoordinator

# Import CycleManager
from .cycle_manager import CycleManager

# Import SentientConfig
from sentientresearchagent.config import SentientConfig


class ExecutionEngine:
    """Orchestrates the overall execution flow of tasks in the graph."""

    def __init__(self, 
                 task_graph: TaskGraph,
                 state_manager: StateManager,
                 knowledge_store: KnowledgeStore,
                 hitl_coordinator: HITLCoordinator,
                 config: Optional[SentientConfig] = None,  # NEW: Add config parameter
                 # Allow NodeProcessor to be passed in for testing or custom setups,
                 # but create a default one if not provided.
                 node_processor: Optional[NodeProcessor] = None, 
                 initial_agent_blueprint_name: Optional[str] = "DeepResearchAgent" # MODIFIED: Added blueprint name with default
                ):
        self.task_graph = task_graph
        self.config = config or SentientConfig()  # NEW: Store config
        
        if node_processor:
            self.node_processor = node_processor
        else:
            # MODIFIED: Pass agent_blueprint_name to NodeProcessor constructor
            self.node_processor = NodeProcessor(
                task_graph=self.task_graph,
                knowledge_store=knowledge_store, 
                config=self.config,  # NEW: Pass config
                agent_blueprint_name=initial_agent_blueprint_name
            )
            
        self.state_manager = state_manager
        self.knowledge_store = knowledge_store 
        self.hitl_coordinator = hitl_coordinator 
        self.project_initializer = ProjectInitializer() 
        self.cycle_manager = CycleManager() 
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
        Complete project flow: Initializes project, performs HITL on root node, then runs execution cycle.
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

        await self.hitl_coordinator.review_initial_project_goal(
            root_node=root_node, # type: ignore
            task_graph=self.task_graph,
            knowledge_store=self.knowledge_store
        )
        
        current_root_node_status = self.task_graph.get_node("root").status # Re-fetch status after HITL
        if current_root_node_status in [TaskStatus.CANCELLED, TaskStatus.FAILED]: # type: ignore
            logger.warning(f"ExecutionEngine: Root node processing halted (status: {current_root_node_status.name}) after initial HITL review. Full execution cycle will not run.") # type: ignore
            self._log_final_statuses() 
            return self.task_graph.get_node("root").result # type: ignore

        logger.info("ExecutionEngine: Root goal review complete. Proceeding to execution cycle.")
        return await self.run_cycle(max_steps)

    async def run_cycle(self, max_steps: Optional[int] = None):
        """Runs the execution loop for a specified number of steps or until completion/deadlock."""
        # Use config default if max_steps not provided
        max_steps = max_steps or self.config.execution.max_execution_steps
        
        logger.info(f"\n--- Starting Execution Cycle (max_steps: {max_steps}) ---")
        
        root_node_initial_check = self.task_graph.get_node("root")
        if not self.task_graph.root_graph_id or not root_node_initial_check:
            logger.error("ExecutionEngine: Project not initialized properly or root node missing before cycle start.")
            return None
        if root_node_initial_check.status in [TaskStatus.CANCELLED, TaskStatus.FAILED]:
            logger.warning(f"ExecutionEngine: Root node is already {root_node_initial_check.status.name}. Cycle may not run effectively.")
            self._log_final_statuses()
            return root_node_initial_check.result

        for step in range(max_steps):
            logger.info(f"\n--- Execution Step {step + 1} of {max_steps} ---")
            
            # Delegate step execution to CycleManager
            processed_in_step = await self.cycle_manager.execute_step(
                task_graph=self.task_graph,
                state_manager=self.state_manager,
                node_processor=self.node_processor, # type: ignore
                knowledge_store=self.knowledge_store
            )
            
            # --- Check for completion or deadlock for this step ---
            active_statuses = {TaskStatus.PENDING, TaskStatus.READY, TaskStatus.RUNNING, TaskStatus.PLAN_DONE, TaskStatus.AGGREGATING, TaskStatus.NEEDS_REPLAN}
            all_nodes_after_step = self.task_graph.get_all_nodes() 

            if not any(n.status in active_statuses for n in all_nodes_after_step):
                logger.success("\n--- Execution Finished: No active nodes left. ---")
                break

            if not processed_in_step and any(n.status in active_statuses for n in all_nodes_after_step):
                logger.error("\n--- Execution Halted: No progress made in this step by CycleManager. Possible deadlock or logic error. ---")
                for n_active in all_nodes_after_step:
                    if n_active.status in active_statuses:
                        logger.error(f"    - Active: {n_active.task_id}, Status: {n_active.status.name}, Goal: '{n_active.goal[:50]}...'")
                break 
        
        if step == max_steps - 1: # type: ignore # Check if loop completed due to max_steps
             # Check active nodes one last time if loop finished due to max_steps
            if any(n.status in active_statuses for n in self.task_graph.get_all_nodes()): # type: ignore
                 logger.warning("\n--- Execution Finished: Reached max steps with active nodes remaining. ---")

        self._log_final_statuses()
        
        root_node_final = self.task_graph.get_node("root")
        return root_node_final.result if root_node_final else None

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
