from typing import Optional, Any, cast
from loguru import logger

from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskStatus, NodeType, TaskType
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import (
    AgentTaskInput, PlanOutput, ReplanRequestDetails, CustomSearcherOutput, PlanModifierInput
) # AtomizerOutput is used by NodeAtomizer, not directly here
from sentientresearchagent.hierarchical_agent_framework.agents.registry import get_agent_adapter
from sentientresearchagent.hierarchical_agent_framework.context.context_builder import (
    resolve_context_for_agent,
)
from sentientresearchagent.hierarchical_agent_framework.context.planner_context_builder import resolve_input_for_planner_agent
from pydantic import BaseModel # For result type checking

from .inode_handler import INodeHandler, ProcessorContext # Import ProcessorContext from here


class ReadyPlanHandler(INodeHandler):
    """Handles a READY node that needs to be PLANNED."""
    async def handle(self, node: TaskNode, context: ProcessorContext) -> None:
        logger.info(f"    ReadyPlanHandler: Planning for node {node.task_id} (Goal: '{node.goal[:50]}...')")
        current_overall_objective = node.overall_objective or getattr(context.task_graph, 'overall_project_goal', "Undefined overall project goal")

        planner_adapter = get_agent_adapter(node, action_verb="plan")
        if not planner_adapter:
            error_msg = f"No PLAN adapter found for node {node.task_id} (TaskType: {node.task_type})"
            logger.error(error_msg)
            node.update_status(TaskStatus.FAILED, error_msg=error_msg)
            return

        current_planner_input_model = resolve_input_for_planner_agent(
            current_task_id=node.task_id,
            knowledge_store=context.knowledge_store,
            overall_objective=current_overall_objective,
            planning_depth=node.layer,
            replan_details=None,
            global_constraints=getattr(context.task_graph, 'global_constraints', [])
        )
        node.input_payload_dict = current_planner_input_model.model_dump()

        plan_output: Optional[PlanOutput] = await planner_adapter.process(node, current_planner_input_model)

        if plan_output is None or not plan_output.sub_tasks:
            if node.status not in [TaskStatus.CANCELLED, TaskStatus.FAILED]:
                logger.warning(f"    Node {node.task_id} (PLAN): Planner returned no sub-tasks or None.")
                if plan_output is None:
                    node.update_status(TaskStatus.FAILED, error_msg="Planner failed to produce an output.")
                else:
                    logger.info(f"    Node {node.task_id} (PLAN): Planner returned an empty list of sub-tasks. Interpreting as task being atomic.")
                    node.node_type = NodeType.EXECUTE
                    node.output_summary = "Planner determined no further sub-tasks are needed; task is atomic."
                    node.update_status(TaskStatus.PLAN_DONE) # Still PLAN_DONE, but next stage will see it as EXECUTE
            return

        hitl_outcome_plan = await context.hitl_coordinator.review_plan_generation(
            node=node,
            plan_output=plan_output,
            planner_input=current_planner_input_model
        )

        if hitl_outcome_plan["status"] == "request_modification":
            logger.info(f"Node {node.task_id}: Plan modification requested by user. Setting to NEEDS_REPLAN.")
            
            modification_instructions = hitl_outcome_plan.get('modification_instructions', 'User requested modification of the plan via HITL.')
            
            node.replan_details = ReplanRequestDetails(
                failed_sub_goal=node.goal,
                reason_for_failure_or_replan=modification_instructions,
                specific_guidance_for_replan=modification_instructions
            )
            
            # Crucial: Populate aux_data for PlanModifierAgent
            node.aux_data['original_plan_for_modification'] = plan_output # plan_output is the PlanOutput model instance
            node.aux_data['user_modification_instructions'] = modification_instructions # This is the string from HITL

            node.replan_reason = f"User requested modification: {modification_instructions[:100]}..." if len(modification_instructions) > 100 else modification_instructions
            node.update_status(TaskStatus.NEEDS_REPLAN)
            # node.result = plan_output # Storing the plan to be modified in result is also an option, but aux_data is cleaner for specific agent inputs
            node.output_summary = "Initial plan requires user modification. Awaiting replan."
            return
        elif hitl_outcome_plan["status"] != "approved":
            return

        context.sub_node_creator.create_sub_nodes(node, plan_output)
        node.result = plan_output
        node.output_summary = f"Planned {len(plan_output.sub_tasks)} sub-tasks."
        node.update_status(TaskStatus.PLAN_DONE)
        logger.success(f"    ReadyPlanHandler: Node {node.task_id} planning complete. Status: {node.status.name}")


class ReadyExecuteHandler(INodeHandler):
    """Handles a READY node that needs to be EXECUTED."""
    async def handle(self, node: TaskNode, context: ProcessorContext) -> None:
        logger.info(f"    ReadyExecuteHandler: Executing node {node.task_id} (Goal: '{node.goal[:50]}...')")

        agent_task_input_model = resolve_context_for_agent(
            current_task_id=node.task_id,
            current_goal=node.goal,
            current_task_type=node.task_type.value if isinstance(node.task_type, TaskType) else str(node.task_type),
            knowledge_store=context.knowledge_store,
            agent_name=node.agent_name,
            overall_project_goal=context.task_graph.overall_project_goal
        )
        node.input_payload_dict = agent_task_input_model.model_dump()

        hitl_outcome_exec = await context.hitl_coordinator.review_before_execution(
            node=node,
            agent_task_input=agent_task_input_model
        )
        if hitl_outcome_exec["status"] != "approved":
            return

        executor_adapter = get_agent_adapter(node, action_verb="execute")
        if not executor_adapter:
            error_msg = f"No EXECUTE adapter found for node {node.task_id} (TaskType: {node.task_type}, NodeType: {node.node_type})"
            logger.error(error_msg)
            node.update_status(TaskStatus.FAILED, error_msg=error_msg)
            return

        adapter_display_name = getattr(executor_adapter, 'agent_name', type(executor_adapter).__name__)
        logger.info(f"    ReadyExecuteHandler: Calling executor adapter '{adapter_display_name}' for node {node.task_id}")
        execution_result: Optional[Any] = await executor_adapter.process(node, agent_task_input_model)

        if execution_result is not None:
            node.result = execution_result
            if isinstance(execution_result, BaseModel):
                try:
                    if hasattr(execution_result, 'summary') and execution_result.summary: # type: ignore
                        node.output_summary = str(execution_result.summary) # type: ignore
                    elif hasattr(execution_result, 'content_summary') and execution_result.content_summary: # type: ignore
                        node.output_summary = str(execution_result.content_summary) # type: ignore
                    elif isinstance(execution_result, CustomSearcherOutput):
                        summary_text = str(execution_result)[:100] + "..." if len(str(execution_result)) > 100 else str(execution_result)
                        annotation_count = len(execution_result.annotations) if execution_result.annotations else 0
                        node.output_summary = f"Search result: \"{summary_text}\" ({annotation_count} annotations)"
                    elif isinstance(execution_result, PlanModifierInput):
                        node.output_summary = "Plan modification result."
                    else:
                        node.output_summary = f"Execution completed. Result type: {type(execution_result).__name__}"
                except Exception as e_summary:
                    logger.warning(f"Error generating summary from BaseModel result for {node.task_id}: {e_summary}")
                    node.output_summary = f"Execution completed. Result type: {type(execution_result).__name__} (summary error)."
            elif isinstance(execution_result, str):
                node.output_summary = execution_result[:250] + "..." if len(execution_result) > 250 else execution_result
            else:
                node.output_summary = f"Execution completed. Data stored in result."
            
            node.update_status(TaskStatus.DONE)
            logger.success(f"    ReadyExecuteHandler: Node {node.task_id} execution complete. Status: {node.status.name}.")
        else:
            if node.status not in [TaskStatus.CANCELLED, TaskStatus.FAILED]:
                logger.warning(f"    ReadyExecuteHandler: Executor for {node.task_id} returned None. Marking as FAILED if not already handled.")
                node.update_status(TaskStatus.FAILED, error_msg="Executor returned no result.")


class ReadyNodeHandler(INodeHandler):
    """Handles a node in READY status, determining if it needs atomization, planning, or execution."""
    def __init__(self, ready_plan_handler: ReadyPlanHandler, ready_execute_handler: ReadyExecuteHandler):
        self.ready_plan_handler = ready_plan_handler
        self.ready_execute_handler = ready_execute_handler

    async def handle(self, node: TaskNode, context: ProcessorContext) -> None:
        logger.info(f"  ReadyNodeHandler: Handling READY node {node.task_id} (Original NodeType: {node.node_type}, Goal: '{node.goal[:30]}...')")
        node.update_status(TaskStatus.RUNNING)
        
        action_to_take_after_atomizer = await context.node_atomizer.atomize_node(node, context.task_graph, context.knowledge_store)

        if action_to_take_after_atomizer is None:
            logger.info(f"Node {node.task_id} processing halted after atomizer/HITL attempt.")
            # Node status should be updated by atomizer or HITLCoordinator
            return

        # node.node_type is updated by atomize_node
        if node.node_type == NodeType.PLAN and node.layer >= context.config.max_planning_layer:
            logger.warning(f"    ReadyNodeHandler: Max planning depth ({context.config.max_planning_layer}) reached for {node.task_id}. Forcing EXECUTE.")
            node.node_type = NodeType.EXECUTE
        
        current_action_type = node.node_type

        if current_action_type == NodeType.PLAN:
            await self.ready_plan_handler.handle(node, context)
        elif current_action_type == NodeType.EXECUTE:
            await self.ready_execute_handler.handle(node, context)
        elif current_action_type == NodeType.AGGREGATE: # Should not happen if atomizer works correctly
            logger.error(f"Node {node.task_id} is AGGREGATE type but was handled in READY state pathway inappropriately.")
            node.update_status(TaskStatus.FAILED, error_msg=f"Node {node.task_id} is AGGREGATE type but was handled in READY state pathway inappropriately.")
        else:
            logger.error(f"Node {node.task_id}: Unhandled NodeType '{node.node_type}' in ReadyNodeHandler after atomization.")
            node.update_status(TaskStatus.FAILED, error_msg=f"Unhandled NodeType '{node.node_type}' for READY node.")


class AggregatingNodeHandler(INodeHandler):
    """Handles a node in AGGREGATING status."""
    async def handle(self, node: TaskNode, context: ProcessorContext) -> None:
        logger.info(f"  AggregatingNodeHandler: Handling AGGREGATING node {node.task_id} (Goal: '{node.goal[:30]}...')")
        node.update_status(TaskStatus.RUNNING)
        # context.knowledge_store.add_or_update_record_from_node(node) # Done in process_node finally

        child_results_for_aggregator: list = [] # Using generic list for content
        if node.sub_graph_id:
            child_nodes = context.task_graph.get_nodes_in_graph(node.sub_graph_id)
            for child_node in child_nodes:
                child_status = child_node.status if isinstance(child_node.status, TaskStatus) else TaskStatus(str(child_node.status))
                if child_status in [TaskStatus.DONE, TaskStatus.FAILED]:
                     child_results_for_aggregator.append(AgentTaskInput.ContextItem( # type: ignore
                        source_task_id=child_node.task_id,
                        source_task_goal=child_node.goal,
                        content=child_node.result if child_status == TaskStatus.DONE else child_node.error,
                        content_type_description=f"child_{child_status.value.lower()}_output"
                    ))
        
        agent_task_input = AgentTaskInput(
            current_task_id=node.task_id,
            current_goal=node.goal,
            current_task_type=TaskType.AGGREGATE.value,
            relevant_context_items=child_results_for_aggregator, # type: ignore
            overall_project_goal=context.task_graph.overall_project_goal
        )
        node.input_payload_dict = agent_task_input.model_dump()
        logger.debug(f"Node {node.task_id} input payload (aggregator): {node.input_payload_dict}")

        if not isinstance(node.node_type, NodeType): # Ensure enum
            node.node_type = NodeType(str(node.node_type))

        aggregator_adapter = get_agent_adapter(node, action_verb="aggregate")
        if not aggregator_adapter:
            logger.error(f"No AGGREGATE adapter found for node {node.task_id}")
            node.update_status(TaskStatus.FAILED, error_msg=f"No AGGREGATE adapter found for node {node.task_id}")
            return

        logger.info(f"    AggregatingNodeHandler: Invoking AGGREGATE adapter '{type(aggregator_adapter).__name__}' for {node.task_id}")
        aggregated_result = await aggregator_adapter.process(node, agent_task_input)
        
        node.output_type_description = "aggregated_text_result" # type: ignore
        node.update_status(TaskStatus.DONE, result=aggregated_result)
        logger.success(f"    AggregatingNodeHandler: Node {node.task_id} aggregation complete. Status: {node.status.name}.")


class NeedsReplanNodeHandler(INodeHandler):
    """Handles a node in NEEDS_REPLAN status."""
    async def handle(self, node: TaskNode, context: ProcessorContext) -> None:
        logger.info(f"  NeedsReplanNodeHandler: Handling NEEDS_REPLAN node {node.task_id} (Replan Attempts: {node.replan_attempts}, Goal: '{node.goal[:30]}...')")

        if node.replan_attempts >= context.config.max_replan_attempts:
            logger.warning(f"    Node {node.task_id}: Max replan attempts ({context.config.max_replan_attempts}) reached. Marking as FAILED.")
            node.update_status(TaskStatus.FAILED, error_msg="Max replan attempts reached.")
            return

        node.replan_attempts += 1
        node.update_status(TaskStatus.RUNNING)
        node.node_type = NodeType.PLAN # Replanning is always a PLAN operation for this handler

        current_overall_objective = node.overall_objective or getattr(context.task_graph, 'overall_project_goal', "Undefined overall project goal")
        new_plan_output: Optional[PlanOutput] = None
        
        # Attempt to get a specialized 'modify_plan' adapter
        active_adapter = get_agent_adapter(node, action_verb="modify_plan")
        is_modifier_agent = True

        if not active_adapter:
            logger.warning(f"No 'modify_plan' adapter found for {node.task_id}. Falling back to default 'plan' adapter for replan.")
            active_adapter = get_agent_adapter(node, action_verb="plan")
            is_modifier_agent = False

        if not active_adapter:
            error_msg = f"No suitable PLAN or MODIFY_PLAN adapter found for node {node.task_id} for replanning."
            logger.error(error_msg)
            node.update_status(TaskStatus.FAILED, error_msg=error_msg)
            return

        if is_modifier_agent:
            # Use PlanModifierInput
            original_plan = node.aux_data.get('original_plan_for_modification')
            user_instructions = node.aux_data.get('user_modification_instructions')

            if not isinstance(original_plan, PlanOutput) or not user_instructions:
                err_msg = f"Node {node.task_id}: Missing original_plan or user_instructions in aux_data for PlanModifierAgent."
                logger.error(err_msg)
                node.update_status(TaskStatus.FAILED, error_msg=err_msg)
                return

            modifier_input = PlanModifierInput(
                original_plan=original_plan,
                user_modification_instructions=user_instructions,
                overall_objective=current_overall_objective,
                parent_task_id=node.parent_node_id,
                planning_depth=node.layer
            )
            node.input_payload_dict = modifier_input.model_dump()
            logger.info(f"    NeedsReplanNodeHandler: Using PlanModifierAgent for {node.task_id}")
            new_plan_output = await active_adapter.process(node, modifier_input)
        else:
            # Fallback to standard Planner: Use PlannerInput with node.replan_details
            logger.info(f"    NeedsReplanNodeHandler: Using standard PlannerAgent for replan of {node.task_id}")
            
            # node.replan_details should be an instance of ReplanRequestDetails or None.
            # It was set in ReadyPlanHandler during HITL modification request.
            if not isinstance(node.replan_details, ReplanRequestDetails) and node.replan_details is not None:
                err_msg = (f"Node {node.task_id}: replan_details is malformed. "
                           f"Expected ReplanRequestDetails instance or None, got {type(node.replan_details)}. "
                           f"Value: {str(node.replan_details)[:200]}")
                logger.error(err_msg)
                # This indicates a deeper issue if node.replan_details is not what ReadyPlanHandler set.
                # Forcing a FAILED state.
                node.update_status(TaskStatus.FAILED, error_msg="Internal error: Malformed replan_details for standard replan.")
                return
            
            planner_input_for_replan = resolve_input_for_planner_agent(
                current_task_id=node.task_id,
                knowledge_store=context.knowledge_store,
                overall_objective=current_overall_objective,
                planning_depth=node.layer,
                replan_details=node.replan_details, # This is the critical line: pass the instance directly
                global_constraints=getattr(context.task_graph, 'global_constraints', [])
            )
            node.input_payload_dict = planner_input_for_replan.model_dump()
            new_plan_output = await active_adapter.process(node, planner_input_for_replan)

        # Process the new_plan_output from either adapter
        if new_plan_output is None or not new_plan_output.sub_tasks:
            if node.status not in [TaskStatus.CANCELLED, TaskStatus.FAILED]: # Avoid overriding terminal status
                logger.warning(f"    Node {node.task_id} (REPLAN): Adapter returned no sub-tasks or None. Replan attempt {node.replan_attempts} failed to produce a new plan.")
                # Decide if this should be a FAILED state or allow more replan attempts if under limit
                # For now, let's consider it a failed replan attempt but not necessarily a final FAILED status for the node unless max attempts are hit.
                # We keep it RUNNING, and the loop in execution_engine will pick it up again if it's still NEEDS_REPLAN or handle if max attempts reached.
                # However, if the adapter explicitly failed and set status, respect that.
                # To signify this attempt failed, we might want a more specific error or keep node.result as None.
                node.output_summary = f"Replan attempt {node.replan_attempts} did not produce a new valid plan."
                # If it's still under max_replan_attempts, it will cycle again. If not, the check at the start of the handler will fail it.
                # No status change here to allow retry logic to take effect.
            return # Exit handler for this step

        # Successful replan, create new sub-nodes
        # First, clean up any old sub-nodes if necessary (depends on graph logic, assuming for now new plan replaces old)
        # This might involve archiving or deleting nodes in node.sub_graph_id if it exists.
        # For simplicity, we assume sub_node_creator handles replacing/creating new graph.
        if node.sub_graph_id:
            logger.info(f"Node {node.task_id}: Existing sub-graph {node.sub_graph_id} might be replaced due to replan.")
            # Potentially: context.task_graph.archive_graph(node.sub_graph_id) or similar cleanup

        context.sub_node_creator.create_sub_nodes(node, new_plan_output)
        node.result = new_plan_output # Store the new plan
        node.replan_details = None # Clear replan details as replan is now done
        node.replan_reason = None   # Clear the reason as well
        # node.output_summary should be updated by create_sub_nodes or here
        node.output_summary = f"Successfully replanned with {len(new_plan_output.sub_tasks)} sub-tasks after {node.replan_attempts} attempt(s)."
        node.update_status(TaskStatus.PLAN_DONE) # Replanning complete, new plan established
        logger.success(f"    NeedsReplanNodeHandler: Node {node.task_id} replanning complete. New plan generated. Status: {node.status.name}")
