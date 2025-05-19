from loguru import logger
from sentientresearchagent.hierarchical_agent_framework.graph.task_graph import TaskGraph
# NodeProcessor will be defined later, so we use a forward reference or Any for now
# from sentientresearchagent.hierarchical_agent_framework.node.node_processor import NodeProcessor
from typing import Any as NodeProcessorType # Placeholder for NodeProcessor
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskStatus, NodeType, TaskType
from sentientresearchagent.hierarchical_agent_framework.graph.state_manager import StateManager
from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import KnowledgeStore # For logging to KS

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
        """Sets up the initial root node for the project."""
        if self.task_graph.root_graph_id is not None:
            logger.warning("Project already initialized or root graph exists.")
            # Potentially load existing state or raise error
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

        # if self.viz_handler: ...

        logger.success(f"Initialized with root node: {root_node.task_id} in graph {root_graph_id}")

    async def run_cycle(self, max_steps: int = 250):
        """Runs the execution loop for a specified number of steps or until completion/deadlock."""
        logger.info("\n--- Starting Execution Cycle ---")
        
        if not self.task_graph.root_graph_id or not self.task_graph.get_node("root"):
            logger.error("Project not initialized. Please call initialize_project first.")
            return None

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
                        self.knowledge_store.add_or_update_record_from_node(node) # Update KS
                        processed_in_step = True
                        logger.info(f"  Transition: Node {node.task_id} PENDING -> READY")


            # --- 2. Process one READY or AGGREGATING node ---
            # Prioritize AGGREGATING nodes to free up parent PLAN nodes sooner
            # Then process READY nodes. Could be more sophisticated (e.g., by layer).
            
            node_to_process = next((n for n in all_nodes if n.status == TaskStatus.AGGREGATING), None)
            if not node_to_process:
                node_to_process = next((n for n in all_nodes if n.status == TaskStatus.READY), None)

            if node_to_process:
                logger.info(f"  Processing Node: {node_to_process.task_id} (Status: {node_to_process.status.name}, Layer: {node_to_process.layer})")
                
                # NodeProcessor will handle changing status to RUNNING, and then to its outcome.
                await self.node_processor.process_node(node_to_process, self.task_graph, self.knowledge_store)
                # After processing, node status and KS record are updated by NodeProcessor
                
                processed_in_step = True
                # After a node is processed, its state (and potentially others) might change,
                # so we continue to the next step to re-evaluate.
                # The node_processor should update the node's status (e.g. to RUNNING, then to PLAN_DONE/DONE/FAILED)
                # and log to knowledge_store.
                continue 

            # --- 3. Update PLAN_DONE -> AGGREGATING transitions ---
            logger.debug(f"ExecutionEngine (Step {step + 1}): Entering PLAN_DONE check. processed_in_step = {processed_in_step}")
            root_node_in_all_nodes = next((n for n in all_nodes if n.task_id == "root"), None)
            if root_node_in_all_nodes:
                logger.debug(f"ExecutionEngine (Step {step + 1}): Root node status in all_nodes for PLAN_DONE check: {root_node_in_all_nodes.status}")
            else:
                logger.debug(f"ExecutionEngine (Step {step + 1}): Root node NOT FOUND in all_nodes for PLAN_DONE check.")
            
            for node in all_nodes:
                if node.status == TaskStatus.PLAN_DONE: 
                    logger.debug(f"ExecutionEngine: Checking can_aggregate for PLAN_DONE node {node.task_id} (Type: {node.node_type})")
                    if self.state_manager.can_aggregate(node):
                        node.update_status(TaskStatus.AGGREGATING)
                        self.knowledge_store.add_or_update_record_from_node(node) # Update KS
                        processed_in_step = True
                        logger.info(f"  Transition: Node {node.task_id} PLAN_DONE -> AGGREGATING")

            # --- Check for completion or deadlock ---
            active_statuses = {TaskStatus.PENDING, TaskStatus.READY, TaskStatus.RUNNING, TaskStatus.PLAN_DONE, TaskStatus.AGGREGATING}
            # Re-fetch all_nodes as their statuses might have changed
            all_nodes = self.task_graph.get_all_nodes()
            if not any(n.status in active_statuses for n in all_nodes):
                logger.success("\n--- Execution Finished: No active nodes left. ---")
                break

            if not processed_in_step and any(n.status in active_statuses for n in all_nodes):
                logger.error("\n--- Execution Halted: No progress made in this step. Possible deadlock or incomplete logic. ---")
                # You might want to log current states of all active nodes here for debugging
                for n in all_nodes:
                    if n.status in active_statuses:
                        logger.error(f"    - Active: {n.task_id}, Status: {n.status.name}, Goal: '{n.goal[:50]}...'")
                break
        
        if step == max_steps -1 and any(n.status in active_statuses for n in self.task_graph.get_all_nodes()):
            logger.warning("\n--- Execution Finished: Reached max steps. ---")

        # Print final results
        self._log_final_statuses()
        
        root_node_final = self.task_graph.get_node("root")
        if root_node_final:
            logger.success(f"\nRoot Task ('{root_node_final.goal}') Final Result:")
            # Consider logging this with logger.debug or a more structured way if too verbose for INFO
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
