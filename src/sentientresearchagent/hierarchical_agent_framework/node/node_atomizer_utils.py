from typing import Optional, Callable, Any, Dict
from loguru import logger

from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskType, NodeType, TaskStatus
from sentientresearchagent.hierarchical_agent_framework.graph.task_graph import TaskGraph
from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import KnowledgeStore
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import AtomizerOutput
from sentientresearchagent.hierarchical_agent_framework.agents.registry import get_agent_adapter
from sentientresearchagent.hierarchical_agent_framework.context.context_builder import resolve_context_for_agent
from sentientresearchagent.hierarchical_agent_framework.agents.utils import get_context_summary
# Import NodeProcessorConfig from its new location
from sentientresearchagent.hierarchical_agent_framework.node.node_configs import NodeProcessorConfig


class NodeAtomizer:
    """
    Responsible for determining if a node's goal is atomic using an Atomizer agent
    and handling associated HITL interactions.
    """
    def __init__(self, 
                 config: NodeProcessorConfig, 
                 hitl_callback: Callable): # hitl_callback is _call_hitl from NodeProcessor
        self.config = config
        self.hitl_callback = hitl_callback # Store the callback

    async def atomize_node(
        self, node: TaskNode, task_graph: TaskGraph, knowledge_store: KnowledgeStore
    ) -> Optional[NodeType]:
        """
        Calls the Atomizer agent to determine if the node's goal is atomic.
        Updates node.goal and node.node_type based on atomizer output.
        Handles HITL after atomization if enabled.
        Returns the NodeType to proceed with (PLAN or EXECUTE), or None if HITL caused an abort/error.
        """
        current_task_type_value = node.task_type.value if isinstance(node.task_type, TaskType) else str(node.task_type)
        
        atomizer_input_model = resolve_context_for_agent(
            current_task_id=node.task_id,
            current_goal=node.goal,
            current_task_type=current_task_type_value,
            agent_name="default_atomizer", # Atomizer typically has a fixed/default name
            knowledge_store=knowledge_store,
            overall_project_goal=task_graph.overall_project_goal
        )
        
        # The node's task_type for get_agent_adapter might not be relevant for choosing atomizer,
        # as atomizer is a specific role. Using a fixed action_verb.
        atomizer_adapter = get_agent_adapter(node, action_verb="atomize") 
        action_to_take: NodeType

        if atomizer_adapter:
            logger.info(f"    NodeAtomizer: Calling Atomizer for node {node.task_id} ('{node.goal[:30]}...')")
            atomizer_output: Optional[AtomizerOutput] = await atomizer_adapter.process(node, atomizer_input_model)
            
            if atomizer_output is None:
                logger.warning(f"    NodeAtomizer: Atomizer for {node.task_id} returned None. Assuming not atomic and needs planning.")
                # This path implies the adapter itself handled any critical failure or HITL abort that led to None
                # If node status isn't already FAILED/CANCELLED, it might need to be set here or default to PLAN
                if node.status not in [TaskStatus.FAILED, TaskStatus.CANCELLED]: # type: ignore
                     node.update_status(TaskStatus.FAILED, error_msg="Atomizer returned None, cannot determine next step.") # type: ignore
                return None # Cannot proceed if atomizer fails to give output

            if atomizer_output.updated_goal != node.goal:
                logger.info(f"    Atomizer updated goal for {node.task_id}: '{node.goal[:50]}...' -> '{atomizer_output.updated_goal[:50]}...'")
                node.goal = atomizer_output.updated_goal
            
            action_to_take = NodeType.EXECUTE if atomizer_output.is_atomic else NodeType.PLAN
            node.node_type = action_to_take # Update the node directly
            
            logger.info(f"    Atomizer determined {node.task_id} as {action_to_take.name}. Node's NodeType set to {node.node_type.name}.")

            if self.config.enable_hitl_after_atomizer:
                hitl_context_msg = f"Review Atomizer output for task '{node.task_id}'. Original goal: '{atomizer_input_model.current_goal}'. Proposed: '{node.goal}'. Action: {action_to_take.name}."
                hitl_data = {
                    "original_goal": atomizer_input_model.current_goal,
                    "updated_goal": node.goal,
                    "atomizer_decision_is_atomic": atomizer_output.is_atomic,
                    "proposed_next_action": action_to_take.value, 
                    "current_context_summary": get_context_summary(atomizer_input_model.relevant_context_items)
                }
                # Use the passed-in HITL callback
                hitl_outcome_atomizer: Dict[str, Any] = await self.hitl_callback(
                    checkpoint_name="PostAtomizerCheck", 
                    context_message=hitl_context_msg, 
                    data_for_review=hitl_data, 
                    node=node
                )
                if hitl_outcome_atomizer.get("status") != "approved": 
                    # Node status should have been updated by the hitl_callback if aborted/failed
                    return None 
            return action_to_take
        else: 
            logger.warning(f"    NodeAtomizer: No AtomizerAdapter found for node {node.task_id}. Defaulting its NodeType based on current value or to EXECUTE.")
            if isinstance(node.node_type, str):
                try:
                    resolved_node_type = NodeType(node.node_type)
                    node.node_type = resolved_node_type
                    return resolved_node_type
                except ValueError:
                    logger.error(f"Invalid NodeType string '{node.node_type}' for node {node.task_id} when atomizer is absent. Defaulting to EXECUTE.")
                    node.node_type = NodeType.EXECUTE
                    return NodeType.EXECUTE
            elif isinstance(node.node_type, NodeType):
                return node.node_type # Already an enum
            else: # If node_type is None or unexpected
                logger.info(f"Node {node.task_id} has no specific NodeType and no atomizer found. Defaulting to EXECUTE.")
                node.node_type = NodeType.EXECUTE
                return NodeType.EXECUTE
