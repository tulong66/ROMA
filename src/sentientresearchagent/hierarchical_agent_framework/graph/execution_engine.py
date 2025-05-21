from loguru import logger
from sentientresearchagent.hierarchical_agent_framework.graph.task_graph import TaskGraph
# NodeProcessor will be defined later, so we use a forward reference or Any for now
# from sentientresearchagent.hierarchical_agent_framework.node.node_processor import NodeProcessor
from typing import Any as NodeProcessorType # Placeholder for NodeProcessor
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskStatus, NodeType, TaskType
from sentientresearchagent.hierarchical_agent_framework.graph.state_manager import StateManager
from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import KnowledgeStore # For logging to KS
from sentientresearchagent.hierarchical_agent_framework.utils.hitl_utils import request_human_review

from agno.exceptions import StopAgentRun # Added import
from typing import Optional, Callable
import pprint # For logging results
import asyncio # Import asyncio


class ExecutionEngine:
    """Orchestrates the overall execution flow of tasks in the graph."""

    def __init__(self, 
                 task_graph: TaskGraph,
                 node_processor: NodeProcessorType, # Actual NodeProcessor instance
                 state_manager: StateManager,
                 knowledge_store: KnowledgeStore): # Added KnowledgeStore
        self.task_graph = task_graph
        self.node_processor = node_processor
        self.state_manager = state_manager
        self.knowledge_store = knowledge_store # Store KS
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
        self.initialize_project(root_goal, root_task_type) # Creates root_node in PENDING status
        
        root_node = self.task_graph.get_node("root")
        if not root_node:
            logger.error("Root node not found after initialization. Cannot proceed.")
            return None

        # Perform HITL for the root node. This might change its goal or status.
        await self._perform_root_node_hitl(root_node)
        
        # Check if HITL resulted in cancellation or failure of the root node
        if root_node.status in [TaskStatus.CANCELLED, TaskStatus.FAILED]:
            logger.warning(f"Root node processing halted due to status {root_node.status.name} after initial HITL review. Full execution cycle will not run.")
            self._log_final_statuses() # Log the final state
            return root_node.result # Or some other indication of halted execution

        # If not cancelled/failed, proceed to the execution cycle.
        # The root node would typically be PENDING here (unless HITL changed status),
        # and run_cycle's first step will move it to READY if appropriate.
        return await self.run_cycle(max_steps)

    async def run_cycle(self, max_steps: int = 250):
        """Runs the execution loop for a specified number of steps or until completion/deadlock."""
        logger.info("\n--- Starting Execution Cycle ---")
        
        if not self.task_graph.root_graph_id or not self.task_graph.get_node("root"):
            logger.error("Project not initialized properly or root node missing.")
            return None
        
        # Initial check for root node status before starting the loop
        root_node_check = self.task_graph.get_node("root")
        if root_node_check and root_node_check.status in [TaskStatus.CANCELLED, TaskStatus.FAILED]:
            logger.warning(f"Root node is already {root_node_check.status.name}. Execution cycle will not proceed effectively.")
            self._log_final_statuses()
            return root_node_check.result

        for step in range(max_steps):
            logger.info(f"\n--- Step {step + 1} of {max_steps} ---")
            processed_in_step = False
            
            all_nodes = self.task_graph.get_all_nodes()
            if not all_nodes:
                logger.warning("No nodes in the graph to process.")
                break

            # --- 1. Update PENDING -> READY transitions ---
            for node in all_nodes:
                if node.status == TaskStatus.PENDING:
                    if self.state_manager.can_become_ready(node):
                        node.update_status(TaskStatus.READY)
                        self.knowledge_store.add_or_update_record_from_node(node)
                        processed_in_step = True
                        logger.info(f"  Transition: Node {node.task_id} PENDING -> READY")

            # --- 2. Process AGGREGATING and/or READY nodes ---
            all_nodes = self.task_graph.get_all_nodes() # Re-fetch after status updates
            aggregating_node_to_process = next((n for n in all_nodes if n.status == TaskStatus.AGGREGATING), None)

            if aggregating_node_to_process:
                logger.info(f"  Processing AGGREGATING Node: {aggregating_node_to_process.task_id} (Status: {aggregating_node_to_process.status.name}, Layer: {aggregating_node_to_process.layer})")
                await self.node_processor.process_node(aggregating_node_to_process, self.task_graph, self.knowledge_store)
                processed_in_step = True
                continue

            ready_nodes = [n for n in all_nodes if n.status == TaskStatus.READY]

            if ready_nodes:
                logger.info(f"  Found {len(ready_nodes)} READY nodes to process in parallel.")
                tasks_to_run = []
                for ready_node in ready_nodes:
                    logger.info(f"    Queueing READY Node for parallel processing: {ready_node.task_id} (Status: {ready_node.status.name}, Layer: {ready_node.layer})")
                    tasks_to_run.append(
                        self.node_processor.process_node(ready_node, self.task_graph, self.knowledge_store)
                    )

                if tasks_to_run:
                    await asyncio.gather(*tasks_to_run)
                    processed_in_step = True
                    continue

            # --- 3. Update PLAN_DONE -> AGGREGATING / NEEDS_REPLAN transitions ---
            logger.debug(f"ExecutionEngine (Step {step + 1}): Entering PLAN_DONE/NEEDS_REPLAN check. processed_in_step = {processed_in_step}")
            all_nodes = self.task_graph.get_all_nodes() 
            
            for node in all_nodes:
                if node.status == TaskStatus.PLAN_DONE: 
                    logger.debug(f"ExecutionEngine: Checking PLAN_DONE node {node.task_id} (Type: {node.node_type}) for aggregation or replan.")
                    if self.state_manager.can_aggregate(node):
                        children_failed = False
                        if node.sub_graph_id:
                            sub_graph_nodes = self.task_graph.get_nodes_in_graph(node.sub_graph_id)
                            if any(sn.status == TaskStatus.FAILED for sn in sub_graph_nodes):
                                children_failed = True
                        
                        if children_failed:
                            node.update_status(TaskStatus.NEEDS_REPLAN)
                            self.knowledge_store.add_or_update_record_from_node(node)
                            processed_in_step = True
                            logger.info(f"  Transition: Node {node.task_id} PLAN_DONE -> NEEDS_REPLAN (due to failed children)")
                        else:
                            node.update_status(TaskStatus.AGGREGATING)
                            self.knowledge_store.add_or_update_record_from_node(node)
                            processed_in_step = True
                            logger.info(f"  Transition: Node {node.task_id} PLAN_DONE -> AGGREGATING")
            
            # --- 4. Process NEEDS_REPLAN nodes ---
            all_nodes = self.task_graph.get_all_nodes() 
            needs_replan_nodes = [n for n in all_nodes if n.status == TaskStatus.NEEDS_REPLAN]
            if needs_replan_nodes:
                node_to_replan = needs_replan_nodes[0] 
                logger.info(f"  Processing NEEDS_REPLAN Node: {node_to_replan.task_id}")
                await self.node_processor._handle_needs_replan_node(node_to_replan, self.task_graph, self.knowledge_store)
                processed_in_step = True
                continue

            # --- Check for completion or deadlock ---
            active_statuses = {TaskStatus.PENDING, TaskStatus.READY, TaskStatus.RUNNING, TaskStatus.PLAN_DONE, TaskStatus.AGGREGATING, TaskStatus.NEEDS_REPLAN}
            all_nodes = self.task_graph.get_all_nodes() 
            if not any(n.status in active_statuses for n in all_nodes):
                logger.success("\n--- Execution Finished: No active nodes left. ---")
                break

            if not processed_in_step and any(n.status in active_statuses for n in all_nodes):
                logger.error("\n--- Execution Halted: No progress made in this step. Possible deadlock or incomplete logic. ---")
                for n in all_nodes:
                    if n.status in active_statuses:
                        logger.error(f"    - Active: {n.task_id}, Status: {n.status.name}, Goal: '{n.goal[:50]}...'")
                break
        
        if step == max_steps -1 and any(n.status in active_statuses for n in self.task_graph.get_all_nodes()):
            logger.warning("\n--- Execution Finished: Reached max steps. ---")

        self._log_final_statuses()
        
        root_node_final = self.task_graph.get_node("root")
        if root_node_final:
            logger.success(f"\nRoot Task ('{root_node_final.goal}') Final Result:")
            logger.info(f"Root Result: {pprint.pformat(root_node_final.result)}")
            return root_node_final.result
        return None

    def _log_final_statuses(self):
        logger.info("\n--- Final Node Statuses & Results ---")
        all_final_nodes = sorted(self.task_graph.get_all_nodes(), key=lambda n: (n.layer, n.task_id))
        for node in all_final_nodes:
            status_str = node.status.name
            
            message = f"- Node {node.task_id} (L{node.layer}, Goal: '{node.goal[:30]}...'): Status={status_str}"
            if node.status == TaskStatus.FAILED and node.error:
                 message += f" (Error: {node.error})"
            
            result_display = str(node.result)
            if len(result_display) > 70: result_display = result_display[:70] + "..."
            message += f", Result='{result_display}'"

            if node.status == TaskStatus.DONE:
                logger.success(message)
            elif node.status == TaskStatus.FAILED:
                logger.error(message)
            else: # PENDING, READY, RUNNING, PLAN_DONE, AGGREGATING, etc.
                logger.warning(message) # Or logger.info if warning is too strong for intermediate states
