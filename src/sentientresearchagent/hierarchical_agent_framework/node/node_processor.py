from typing import List, Optional
from pydantic import BaseModel
from loguru import logger
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskStatus, NodeType, TaskType
from sentientresearchagent.hierarchical_agent_framework.graph.task_graph import TaskGraph
from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import KnowledgeStore
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import (
    AgentTaskInput, PlanOutput, AtomizerOutput, ContextItem,
    PlannerInput, ReplanRequestDetails
)
from sentientresearchagent.hierarchical_agent_framework.agents.registry import get_agent_adapter
from sentientresearchagent.hierarchical_agent_framework.agents.base_adapter import BaseAdapter # For type hinting
from sentientresearchagent.hierarchical_agent_framework.context.context_builder import (
    resolve_context_for_agent,
    resolve_input_for_planner_agent
)

# Configuration
MAX_PLANNING_LAYER = 5 # Max depth for recursive planning

class NodeProcessor:
    """Handles the processing of a single TaskNode's action."""

    def __init__(self):
        # NodeProcessor might not need to store graph_manager or ks if they are passed during process_node
        # However, if context_builder is a member, it might need graph_manager.
        # For now, assuming context_builder will also be instantiated and used locally or passed.
        logger.info("NodeProcessor initialized.")
        # If context_builder becomes complex or needs state, it could be initialized here:
        # self.context_builder = ContextBuilder(task_graph) # If TaskGraph is relatively static or passed on update

    def _create_sub_nodes_from_plan(self, parent_node: TaskNode, plan_output: PlanOutput, task_graph: TaskGraph, knowledge_store: KnowledgeStore):
        """
        Creates TaskNode instances from a plan list, adds them to the graph,
        sets up sequential dependencies, and updates the parent_node.
        """
        if not parent_node.sub_graph_id:
            # This should have been created before calling this function if it's a new plan
            parent_node.sub_graph_id = f"subgraph_{parent_node.task_id}"
            task_graph.add_graph(parent_node.sub_graph_id)
            logger.info(f"    NodeProcessor: Created new subgraph '{parent_node.sub_graph_id}' for parent '{parent_node.task_id}'")
        
        sub_graph_id = parent_node.sub_graph_id
        parent_node.planned_sub_task_ids.clear() # Clear any old sub-tasks if replanning

        created_sub_nodes: list[TaskNode] = []

        for i, sub_task_def in enumerate(plan_output.sub_tasks):
            sub_node_id = f"{parent_node.task_id}.{i+1}" # Simple sequential ID

            try:
                # Validate and convert string types from PlanOutput to Enums for TaskNode
                task_type_enum = TaskType[sub_task_def.task_type.upper()]
                node_type_enum = NodeType[sub_task_def.node_type.upper()]
            except KeyError as e:
                error_msg = f"Invalid task_type or node_type string ('{sub_task_def.task_type}'/'{sub_task_def.node_type}') in plan for parent {parent_node.task_id}: {e}"
                logger.error(f"    NodeProcessor Error: {error_msg}")
                # Optionally, fail the parent node or skip this sub_task
                # For now, let's skip this potentially invalid sub_task
                continue

            sub_node = TaskNode(
                goal=sub_task_def.goal,
                task_type=task_type_enum,
                node_type=node_type_enum,
                task_id=sub_node_id,
                layer=parent_node.layer + 1,
                parent_node_id=parent_node.task_id,
                overall_objective=parent_node.overall_objective
            )
            created_sub_nodes.append(sub_node)
            task_graph.add_node_to_graph(sub_graph_id, sub_node)
            knowledge_store.add_or_update_record_from_node(sub_node) # Log new sub_node
            parent_node.planned_sub_task_ids.append(sub_node.task_id)
            logger.success(f"      Added sub-node: {sub_node} to graph {sub_graph_id}")

        # Add sequential dependencies for now
        for i in range(len(created_sub_nodes) - 1):
            u_node = created_sub_nodes[i]
            v_node = created_sub_nodes[i+1]
            task_graph.add_edge(sub_graph_id, u_node.task_id, v_node.task_id)
        
        logger.info(f"    NodeProcessor: Created {len(created_sub_nodes)} sub-nodes for parent {parent_node.task_id}.")


    def _handle_ready_node(self, node: TaskNode, task_graph: TaskGraph, knowledge_store: KnowledgeStore):
        logger.info(f"  NodeProcessor: Handling READY node {node.task_id} (Type: {node.node_type}, Goal: '{node.goal[:30]}...')")
        node.update_status(TaskStatus.RUNNING) # Mark as RUNNING before agent call
        knowledge_store.add_or_update_record_from_node(node)

        original_node_type = node.node_type
        
        # 1. Atomicity Check (Conceptual - for now, let's assume an atomizer agent is called)
        # In a full implementation, this would involve:
        # - Getting an 'AtomizerAdapter'.
        # - Preparing AgentTaskInput for the atomizer.
        # - Calling adapter.process() to get AtomizerOutput.
        # - Updating node.goal and node.node_type based on AtomizerOutput.
        
        # --- Simplified Atomicity ---
        # For now, we'll skip explicit atomizer call and proceed based on original node_type
        # or simple rules. A real implementation would use an AtomizerAdapter.
        is_atomic_determined = (original_node_type == NodeType.EXECUTE)
        # If it was planned as EXECUTE, assume it's atomic for now.
        # If it was PLAN, it needs planning unless max depth is reached.

        # --- Ensure comparisons use Enum members or string values consistently ---
        # Determine if the original type corresponds to PLAN
        is_plan_type = original_node_type == NodeType.PLAN if isinstance(original_node_type, NodeType) else original_node_type == NodeType.PLAN.value
        
        if is_plan_type and node.layer >= MAX_PLANNING_LAYER:
            logger.warning(f"    NodeProcessor: Max planning depth ({MAX_PLANNING_LAYER}) reached for {node.task_id}. Forcing EXECUTE.")
            node.node_type = NodeType.EXECUTE # Assign Enum member here
            is_atomic_determined = True
        
        # Ensure action_to_take holds the Enum member for later logic
        # If node.node_type might still be string after potential modification:
        action_to_take = node.node_type if isinstance(node.node_type, NodeType) else NodeType(node.node_type)

        # 2. Prepare AgentTaskInput
        current_task_type_value = node.task_type.value if isinstance(node.task_type, TaskType) else node.task_type
        
        # agent_name is no longer part of TaskNode, so it's not used here for resolve_context_for_agent
        # The agent_name parameter in resolve_context_for_agent might need to be re-evaluated 
        # or set to a generic value if it's still required by that function's logic.
        # For now, assuming resolve_context_for_agent can handle agent_name=None or a generic placeholder.
        agent_task_input_model = resolve_context_for_agent(
            current_task_id=node.task_id,
            current_goal=node.goal,
            current_task_type=current_task_type_value, 
            agent_name=f"agent_for_{current_task_type_value}", # Generic placeholder if agent_name is needed by context resolver
            knowledge_store=knowledge_store,
            overall_project_goal=task_graph.overall_project_goal
        )
        node.input_payload_dict = agent_task_input_model.model_dump()
        logger.debug(f"Node {node.task_id} input payload (general): {node.input_payload_dict}")

        try:
            # --- Action based on Enum member ---
            if action_to_take == NodeType.PLAN:
                logger.info(f"    NodeProcessor: Preparing PlannerInput for {node.task_id}")
                
                current_overall_objective = node.overall_objective or getattr(task_graph, 'overall_project_goal', None)
                if not current_overall_objective:
                     logger.warning(f"    NodeProcessor WARNING: overall_objective is not set for node {node.task_id}. Using placeholder.")
                     current_overall_objective = "Undefined overall project goal"

                planner_adapter = get_agent_adapter(node, action_verb="plan")
                if not planner_adapter:
                    # Removed agent_name from error message
                    raise ValueError(f"No PLAN adapter found for node {node.task_id} (TaskType: {node.task_type})")

                planner_input_model = resolve_input_for_planner_agent(
                    current_task_id=node.task_id,
                    knowledge_store=knowledge_store,
                    overall_objective=current_overall_objective,
                    planning_depth=node.layer,
                    replan_details=None, 
                    global_constraints=getattr(task_graph, 'global_constraints', [])
                )
                node.input_payload_dict = planner_input_model.model_dump() # For logging
                plan_output: PlanOutput = planner_adapter.process(node, planner_input_model) # PASSING THE MODEL

                if not plan_output or not plan_output.sub_tasks:
                    logger.warning(f"    NodeProcessor: Planner for {node.task_id} returned no sub-tasks. Converting to EXECUTE.")
                    node.node_type = NodeType.EXECUTE # Set Enum member
                    # Re-prepare context if goal or type changed significantly? (Assume fine for now)
                    self._execute_node_action(node, agent_task_input_model, task_graph, knowledge_store)
                else:
                    self._create_sub_nodes_from_plan(node, plan_output, task_graph, knowledge_store)
                    node.update_status(TaskStatus.PLAN_DONE, result=plan_output.model_dump())
            
            elif action_to_take == NodeType.EXECUTE:
                 self._execute_node_action(node, agent_task_input_model, task_graph, knowledge_store)

            else: # Should not happen if node_type is always PLAN or EXECUTE Enum after conversion
                raise ValueError(f"Unexpected node action type Enum: {action_to_take} for node {node.task_id}")

        except Exception as e:
            logger.error(f"  NodeProcessor Error: Failed to process READY node {node.task_id}: {e}")
            # Ensure status update uses the Enum member
            node.update_status(TaskStatus.FAILED, error_msg=str(e))
        
        knowledge_store.add_or_update_record_from_node(node) # Final update

    def _execute_node_action(self, node: TaskNode, agent_task_input: AgentTaskInput, task_graph: TaskGraph, knowledge_store: KnowledgeStore):
        # Ensure node.node_type is an Enum for get_agent_adapter if it expects one
        if not isinstance(node.node_type, NodeType):
             node.node_type = NodeType(node.node_type) # Convert if necessary
        
        executor_adapter = get_agent_adapter(node, action_verb="execute")
        if not executor_adapter:
             # Ensure TaskType is handled correctly in error message if it could be string
             task_type_display = node.task_type.name if isinstance(node.task_type, TaskType) else node.task_type
             # Removed agent_name from error message
             raise ValueError(f"No EXECUTE adapter found for node {node.task_id} (TaskType: {task_type_display})")

        logger.info(f"    NodeProcessor: Invoking EXECUTE adapter '{type(executor_adapter).__name__}' for {node.task_id}")
        execution_result = executor_adapter.process(node, agent_task_input)
        
        node.output_type_description = f"{type(execution_result).__name__}_result"
        
        if execution_result is not None:
            # TODO: Implement robust summarization.
            # For Pydantic models, check if they have a summary method/attribute.
            if hasattr(execution_result, 'get_summary_for_context') and callable(execution_result.get_summary_for_context):
                node.output_summary = execution_result.get_summary_for_context()
            elif hasattr(execution_result, 'summary'):
                 node.output_summary = str(execution_result.summary)
            elif isinstance(execution_result, str):
                node.output_summary = execution_result[:500] + "..." if len(execution_result) > 500 else execution_result
            elif isinstance(execution_result, BaseModel): # For Pydantic models without specific summary
                try:
                    # Try to get a compact representation, excluding verbose fields if any
                    summary_dict = execution_result.model_dump(exclude_none=True)
                    summary_str = str(summary_dict)
                    node.output_summary = summary_str[:500] + "..." if len(summary_str) > 500 else summary_str
                except Exception:
                    node.output_summary = f"Result of type {type(execution_result).__name__}"
            else:
                node.output_summary = f"Result of type {type(execution_result).__name__}"
            logger.success(f"    NodeProcessor: Set output_summary for {node.task_id}: '{node.output_summary[:100]}...'")

        if isinstance(execution_result, str) and execution_result.startswith("<<NEEDS_REPLAN>>"):
            replan_reason = execution_result.replace("<<NEEDS_REPLAN>>", "").strip()
            logger.warning(f"    NodeProcessor: Node {node.task_id} requested REPLAN. Reason: {replan_reason}")
            # Ensure status update uses the Enum member
            node.update_status(TaskStatus.NEEDS_REPLAN, result=replan_reason)
        else:
            # Ensure status update uses the Enum member
            node.update_status(TaskStatus.DONE, result=execution_result)

    def _handle_aggregating_node(self, node: TaskNode, task_graph: TaskGraph, knowledge_store: KnowledgeStore):
        logger.info(f"  NodeProcessor: Handling AGGREGATING node {node.task_id} (Goal: '{node.goal[:30]}...')")
        node.update_status(TaskStatus.RUNNING) # Mark as RUNNING before agent call
        knowledge_store.add_or_update_record_from_node(node)

        # 1. Prepare AgentTaskInput for the aggregator.
        # The context for an aggregator is typically the results of its children.
        # The `resolve_context_for_agent` should be configured to fetch these.
        # The `current_goal` for the aggregator is the parent (this node's) goal.
        
        # Gather children's results to pass explicitly if `resolve_context_for_agent` doesn't handle it perfectly for aggregators
        # This is a simplified direct gathering; `resolve_context_for_agent` might be more sophisticated.
        child_results_for_aggregator: List[ContextItem] = []
        if node.sub_graph_id:
            child_nodes = task_graph.get_nodes_in_graph(node.sub_graph_id)
            for child_node in child_nodes:
                child_status = child_node.status if isinstance(child_node.status, TaskStatus) else TaskStatus(child_node.status)
                if child_status in [TaskStatus.DONE, TaskStatus.FAILED]:
                     child_results_for_aggregator.append(ContextItem(
                        source_task_id=child_node.task_id,
                        source_task_goal=child_node.goal,
                        content=child_node.result if child_status == TaskStatus.DONE else child_node.error,
                        # Use child_status.value which is the string representation
                        content_type_description=f"child_{child_status.value.lower()}_output" 
                    ))
        
        agent_task_input = AgentTaskInput(
            current_task_id=node.task_id,
            current_goal=node.goal,
            current_task_type=TaskType.AGGREGATE.value, # Aggregation is fixed type
            relevant_context_items=child_results_for_aggregator,
            overall_project_goal=task_graph.overall_project_goal
        )
        node.input_payload_dict = agent_task_input.model_dump() # Log what aggregator will receive
        logger.debug(f"Node {node.task_id} input payload (aggregator): {node.input_payload_dict}")

        try:
            # Ensure node.node_type is Enum for get_agent_adapter if needed
            if not isinstance(node.node_type, NodeType):
                node.node_type = NodeType(node.node_type) # Convert if necessary

            aggregator_adapter = get_agent_adapter(node, action_verb="aggregate")
            if not aggregator_adapter:
                raise ValueError(f"No AGGREGATE adapter found for node {node.task_id}")

            logger.info(f"    NodeProcessor: Invoking AGGREGATE adapter '{type(aggregator_adapter).__name__}' for {node.task_id}")
            aggregated_result = aggregator_adapter.process(node, agent_task_input)
            
            node.output_type_description = "aggregated_text_result"
            # Ensure status update uses the Enum member
            node.update_status(TaskStatus.DONE, result=aggregated_result)

        except Exception as e:
            logger.error(f"  NodeProcessor Error: Failed to process AGGREGATING node {node.task_id}: {e}")
            # Ensure status update uses the Enum member
            node.update_status(TaskStatus.FAILED, error_msg=str(e))
        
        knowledge_store.add_or_update_record_from_node(node) # Final update

    def _handle_needs_replan_node(self, node: TaskNode, task_graph: TaskGraph, knowledge_store: KnowledgeStore):
        logger.info(f"  NodeProcessor: Handling NEEDS_REPLAN node {node.task_id} (Goal: '{node.goal[:30]}...')")
        
        # Mark as RUNNING for the replanning attempt. Could also be a new REPLANNING status.
        node.update_status(TaskStatus.RUNNING, result=f"Attempting to re-plan: {node.result}") 
        knowledge_store.add_or_update_record_from_node(node)

        try:
            # 1. Construct ReplanRequestDetails
            reason_for_replan = str(node.result) if node.result else "No specific reason provided for re-plan."
            # remove the <<NEEDS_REPLAN>> prefix if present, as it's already handled
            if "<<NEEDS_REPLAN>>" in reason_for_replan:
                 reason_for_replan = reason_for_replan.split("<<NEEDS_REPLAN>>",1)[-1].strip()
            
            # previous_attempt_output_summary should be node.output_summary from the failed/problematic execution
            # This assumes output_summary was populated even for tasks that ended up in NEEDS_REPLAN
            prev_summary = node.output_summary if node.output_summary else "No summary of previous attempt available."

            replan_details = ReplanRequestDetails(
                failed_sub_goal=node.goal, # The current node's goal is the one that failed/needs replan
                reason_for_failure_or_replan=reason_for_replan,
                previous_attempt_output_summary=prev_summary,
                specific_guidance_for_replan=None # TODO: Allow agents to provide more specific guidance
            )
            logger.info(f"    Replan Details: {replan_details.model_dump_json(indent=2, exclude_none=True)}")

            # 2. Prepare PlannerInput
            current_overall_objective = node.overall_objective or task_graph.overall_project_goal
            if not current_overall_objective:
                 logger.warning(f"    NodeProcessor WARNING: overall_objective is not set for REPLAN node {node.task_id}. Using placeholder.")
                 current_overall_objective = "Undefined overall project goal"

            planner_adapter = get_agent_adapter(node, action_verb="plan") # Or "replan" if you have a specific replan adapter
            if not planner_adapter:
                # Removed agent_name from error message
                raise ValueError(f"No PLAN/REPLAN adapter found for node {node.task_id} (TaskType: {node.task_type})")

            planner_input_model = resolve_input_for_planner_agent(
                current_task_id=node.task_id,
                knowledge_store=knowledge_store,
                overall_objective=current_overall_objective,
                planning_depth=node.layer, # Use the current node's layer for planning depth
                replan_details=replan_details,
                global_constraints=task_graph.global_constraints if hasattr(task_graph, 'global_constraints') else []
            )
            node.input_payload_dict = planner_input_model.model_dump() # For logging
            plan_output: PlanOutput = planner_adapter.process(node, planner_input_model) # PASSING THE MODEL

            # 4. Process New Plan
            if not plan_output or not plan_output.sub_tasks:
                logger.error(f"    NodeProcessor: Re-Planner for {node.task_id} returned no sub-tasks. Node remains NEEDS_REPLAN or FAILED.")
                # TODO: Implement retry logic or max attempts for re-planning
                node.update_status(TaskStatus.FAILED, error_msg="Re-planning failed to produce sub-tasks.", result=node.result) # Keep original reason in result
            else:
                logger.success(f"    NodeProcessor: Re-Planner for {node.task_id} SUCCEEDED. Creating new sub-nodes.")
                # The node itself (which was the parent of the failed plan, or the failed execute node)
                # will now become a parent to the new sub-tasks.
                # _create_sub_nodes_from_plan will clear node.planned_sub_task_ids
                if not node.sub_graph_id: # Ensure subgraph exists if it was an EXECUTE node being replanned into a PLAN
                     node.sub_graph_id = f"subgraph_{node.task_id}"
                     task_graph.add_graph(node.sub_graph_id)

                self._create_sub_nodes_from_plan(node, plan_output, task_graph, knowledge_store)
                node.node_type = NodeType.PLAN # Explicitly set node_type to PLAN as it now has a sub-plan
                node.update_status(TaskStatus.PLAN_DONE, result=plan_output.model_dump())
                logger.success(f"    NodeProcessor: Node {node.task_id} REPLANNED successfully. Status: PLAN_DONE.")

        except Exception as e:
            logger.exception(f"  NodeProcessor Error: Failed to REPLAN node {node.task_id}")
            node.update_status(TaskStatus.FAILED, error_msg=f"Exception during re-planning: {str(e)}", result=node.result)
        
        knowledge_store.add_or_update_record_from_node(node) # Final update

    def process_node(self, node: TaskNode, task_graph: TaskGraph, knowledge_store: KnowledgeStore):
        """
        Processes a node based on its status.
        This method is called by the ExecutionEngine.
        """
        status_display = node.status.name if isinstance(node.status, TaskStatus) else node.status
        logger.info(f"NodeProcessor: Received node {node.task_id} (Goal: '{node.goal[:30]}...') with status {status_display}")

        current_status = node.status if isinstance(node.status, TaskStatus) else TaskStatus(node.status)
        
        if current_status == TaskStatus.READY:
            self._handle_ready_node(node, task_graph, knowledge_store)
        elif current_status == TaskStatus.AGGREGATING:
            self._handle_aggregating_node(node, task_graph, knowledge_store)
        elif current_status == TaskStatus.NEEDS_REPLAN:
            self._handle_needs_replan_node(node, task_graph, knowledge_store)
        else:
            logger.warning(f"  NodeProcessor Warning: process_node called on node {node.task_id} with status {status_display} - no action taken.")
