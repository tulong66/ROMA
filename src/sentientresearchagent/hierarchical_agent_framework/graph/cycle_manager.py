from loguru import logger
import asyncio
from typing import Any as NodeProcessorType, Optional, Callable # For NodeProcessor type hint

from sentientresearchagent.hierarchical_agent_framework.graph.task_graph import TaskGraph
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskStatus, NodeType, TaskType # NodeType, TaskType might not be directly used here
from sentientresearchagent.hierarchical_agent_framework.graph.state_manager import StateManager
from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import KnowledgeStore
# NodeProcessor itself is passed, not its components separately to CycleManager.
# from sentientresearchagent.hierarchical_agent_framework.node.node_processor import NodeProcessor 


async def _atomic_transition_if_eligible(
    node: TaskNode,
    from_status: TaskStatus,
    to_status: TaskStatus,
    eligibility_check: Callable[[], bool],
    knowledge_store: KnowledgeStore,
    update_callback: Optional[Callable] = None
) -> bool:
    """
    Atomically transitions a node from one status to another if eligible.
    This prevents race conditions where the node status might change between
    the check and the update.
    
    Returns:
        bool: True if transition occurred, False otherwise
    """
    # The node's internal lock ensures atomicity
    if node.status == from_status and eligibility_check():
        node.update_status(to_status)
        knowledge_store.add_or_update_record_from_node(node)
        
        # Trigger update callback for immediate broadcast
        if update_callback:
            try:
                update_callback()
                logger.debug(f"  Atomic transition: Update callback triggered after {from_status} -> {to_status} for {node.task_id}")
            except Exception as e:
                logger.warning(f"  Atomic transition: Update callback failed: {e}")
        
        return True
    return False 

class CycleManager:
    """
    Manages the core logic of a single step within the ExecutionEngine's run_cycle.
    It handles node status transitions and dispatches nodes to the NodeProcessor.
    """

    async def execute_step(
        self,
        task_graph: TaskGraph,
        state_manager: StateManager,
        node_processor: NodeProcessorType, # Actual NodeProcessor instance
        knowledge_store: KnowledgeStore,
        update_callback: Optional[Callable] = None  # Add update callback for broadcasts
    ) -> bool:
        """
        Executes one step of the processing cycle.

        Returns:
            bool: True if any processing or state transition occurred in the step, False otherwise.
        """
        processed_in_step = False
        
        all_nodes_current_step = task_graph.get_all_nodes()
        if not all_nodes_current_step:
            logger.debug("CycleManager: No nodes in the graph to process this step.")
            return False # No nodes, no processing

        # --- 1. Update PENDING -> READY transitions ---
        logger.debug("CycleManager: Checking for PENDING -> READY transitions.")
        for node in all_nodes_current_step:
            # Atomic check-and-update for PENDING -> READY transition
            if await _atomic_transition_if_eligible(node, TaskStatus.PENDING, TaskStatus.READY,
                                                   lambda: state_manager.can_become_ready(node),
                                                   knowledge_store, update_callback):
                processed_in_step = True
                logger.info(f"  CycleManager Transition: Node {node.task_id} PENDING -> READY (Goal: '{node.goal[:30]}...')")

        # --- 2. Process AGGREGATING nodes (serially, one at a time) ---
        # Re-fetch nodes as statuses might have changed
        nodes_after_pending_update = task_graph.get_all_nodes()
        aggregating_node_to_process = next((n for n in nodes_after_pending_update if n.status == TaskStatus.AGGREGATING), None)

        if aggregating_node_to_process:
            logger.info(f"  CycleManager: Processing AGGREGATING Node: {aggregating_node_to_process.task_id} (Layer: {aggregating_node_to_process.layer}, Goal: '{aggregating_node_to_process.goal[:30]}...')")
            await node_processor.process_node(aggregating_node_to_process, task_graph, knowledge_store)
            processed_in_step = True
            # If an AGGREGATING node was processed, it's a significant state change.
            # Return True and let ExecutionEngine loop again to re-evaluate the whole graph state.
            return True # Indicate processing occurred

        # --- 3. Process READY nodes (in parallel) ---
        nodes_for_ready_processing = task_graph.get_all_nodes() # Re-fetch
        ready_nodes = [n for n in nodes_for_ready_processing if n.status == TaskStatus.READY]
        if ready_nodes:
            logger.info(f"  CycleManager: Found {len(ready_nodes)} READY nodes. Queueing for parallel processing.")
            tasks_to_run = [
                node_processor.process_node(ready_node, task_graph, knowledge_store)
                for ready_node in ready_nodes
            ]
            if tasks_to_run:
                await asyncio.gather(*tasks_to_run)
                processed_in_step = True
                # After processing READY nodes, their statuses (e.g. to PLAN_DONE, DONE, FAILED) have changed.
                # Return True. ExecutionEngine will loop and then PLAN_DONE transitions can occur.
                return True # Indicate processing occurred

        # --- 4. Update PLAN_DONE -> AGGREGATING / READY transitions ---
        nodes_for_plan_done_update = task_graph.get_all_nodes()
        made_plan_done_transition = False
        logger.debug("CycleManager: Checking for PLAN_DONE transitions.")
        for node in nodes_for_plan_done_update:
            if node.status == TaskStatus.PLAN_DONE:
                # ENHANCED: Check if this node was converted to EXECUTE type during planning
                if node.node_type == NodeType.EXECUTE:
                    # A PLAN node that becomes EXECUTE is an atomic task
                    if await _atomic_transition_if_eligible(node, TaskStatus.PLAN_DONE, TaskStatus.DONE,
                                                           lambda: True,  # Always eligible if we got here
                                                           knowledge_store, update_callback):
                        logger.info(f"  CycleManager Transition: Node {node.task_id} was atomic. Transitioning PLAN_DONE -> DONE.")
                        processed_in_step = True
                        made_plan_done_transition = True
                # Also check if this was originally an EXECUTE node that somehow got planned
                elif hasattr(node, 'aux_data') and node.aux_data.get('was_executed_as_atomic'):
                    if await _atomic_transition_if_eligible(node, TaskStatus.PLAN_DONE, TaskStatus.DONE,
                                                           lambda: True,  # Always eligible if we got here
                                                           knowledge_store, update_callback):
                        logger.warning(f"  CycleManager: Node {node.task_id} was already executed as atomic but reached PLAN_DONE. Transitioning directly to DONE.")
                        processed_in_step = True
                        made_plan_done_transition = True
                elif state_manager.can_aggregate(node):
                    children_failed = False
                    if node.sub_graph_id:
                        sub_graph_nodes = task_graph.get_nodes_in_graph(node.sub_graph_id)
                        if any(sn.status == TaskStatus.FAILED for sn in sub_graph_nodes):
                            children_failed = True
                    
                    if children_failed:
                        if await _atomic_transition_if_eligible(node, TaskStatus.PLAN_DONE, TaskStatus.NEEDS_REPLAN,
                                                               lambda: True,  # Already checked children_failed
                                                               knowledge_store, update_callback):
                            logger.info(f"  CycleManager Transition: Node {node.task_id} PLAN_DONE -> NEEDS_REPLAN (due to failed children, Goal: '{node.goal[:30]}...')")
                    else:
                        if await _atomic_transition_if_eligible(node, TaskStatus.PLAN_DONE, TaskStatus.AGGREGATING,
                                                               lambda: True,  # Already checked can_aggregate
                                                               knowledge_store, update_callback):
                            logger.info(f"  CycleManager Transition: Node {node.task_id} PLAN_DONE -> AGGREGATING (Goal: '{node.goal[:30]}...')")
                    processed_in_step = True
                    made_plan_done_transition = True
                else:
                    # Node cannot aggregate yet (dependencies not ready)
                    logger.debug(f"Node {node.task_id} cannot AGGREGATE: Not all sub-tasks in '{node.sub_graph_id}' are finished.")
                    # Log which sub-tasks are blocking
                    if node.sub_graph_id:
                        sub_nodes = task_graph.get_nodes_in_graph(node.sub_graph_id)
                        incomplete = [n for n in sub_nodes if n.status not in {TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED}]
                        if incomplete:
                            logger.debug(f"  Blocking sub-tasks for {node.task_id}:")
                            for inc in incomplete[:5]:  # Show first 5
                                logger.debug(f"    - {inc.task_id}: {inc.status.name} (goal: '{inc.goal[:30]}...')")
        
        if made_plan_done_transition:
            return True # Indicate processing occurred

        # --- 5. Process NEEDS_REPLAN nodes (serially, one at a time) ---
        # This runs if no other major processing happened above that caused an early return.
        nodes_for_replan_processing = task_graph.get_all_nodes()
        needs_replan_nodes = [n for n in nodes_for_replan_processing if n.status == TaskStatus.NEEDS_REPLAN]
        if needs_replan_nodes:
            node_to_replan = needs_replan_nodes[0]
            logger.info(f"  CycleManager: Processing NEEDS_REPLAN Node: {node_to_replan.task_id} (Goal: '{node_to_replan.goal[:30]}...')")
            await node_processor.process_node(node_to_replan, task_graph, knowledge_store)
            processed_in_step = True
            # After processing a NEEDS_REPLAN node, its status changes.
            return True # Indicate processing occurred

        return processed_in_step 