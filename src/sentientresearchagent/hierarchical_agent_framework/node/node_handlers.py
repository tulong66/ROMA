from typing import Optional, Any, cast
from loguru import logger

from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskStatus, NodeType, TaskType
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import (
    AgentTaskInput, PlanOutput, ReplanRequestDetails, CustomSearcherOutput, PlanModifierInput, ContextItem
)
from sentientresearchagent.hierarchical_agent_framework.agents.registry import get_agent_adapter
from sentientresearchagent.hierarchical_agent_framework.context.context_builder import (
    resolve_context_for_agent,
)
from sentientresearchagent.hierarchical_agent_framework.context.planner_context_builder import resolve_input_for_planner_agent
from pydantic import BaseModel

from .inode_handler import INodeHandler, ProcessorContext


class ReadyPlanHandler(INodeHandler):
    """Handles a READY node that needs to be PLANNED."""
    async def handle(self, node: TaskNode, context: ProcessorContext) -> None:
        agent_name_at_entry = node.agent_name
        blueprint_name_log = context.current_agent_blueprint.name if context.current_agent_blueprint else "N/A"
        logger.info(f"    ReadyPlanHandler: Planning for node {node.task_id} (Blueprint: {blueprint_name_log}, Goal: '{node.goal[:50]}...', Original Agent Name at Entry: {agent_name_at_entry})")
        
        try:
            current_overall_objective = node.overall_objective or getattr(context.task_graph, 'overall_project_goal', "Undefined overall project goal")
            
            lookup_name_for_planner = agent_name_at_entry
            if context.current_agent_blueprint:
                if context.current_agent_blueprint.planner_adapter_name:
                    lookup_name_for_planner = context.current_agent_blueprint.planner_adapter_name
                    logger.debug(f"        ReadyPlanHandler: Blueprint specifies planner: {lookup_name_for_planner}")
                elif not lookup_name_for_planner and context.current_agent_blueprint.default_node_agent_name_prefix:
                    lookup_name_for_planner = f"{context.current_agent_blueprint.default_node_agent_name_prefix}Planner"
                    logger.debug(f"        ReadyPlanHandler: Blueprint suggests prefix for planner: {lookup_name_for_planner}")

            node.agent_name = lookup_name_for_planner 
            planner_adapter = get_agent_adapter(node, action_verb="plan")

            if not planner_adapter and agent_name_at_entry and node.agent_name != agent_name_at_entry:
                logger.debug(f"        ReadyPlanHandler: Blueprint planner lookup failed. Trying original entry agent_name for plan: {agent_name_at_entry}")
                node.agent_name = agent_name_at_entry
                planner_adapter = get_agent_adapter(node, action_verb="plan")
            
            if not planner_adapter:
                final_tried_name = node.agent_name or lookup_name_for_planner or agent_name_at_entry
                error_msg = f"No PLAN adapter found for node {node.task_id} (TaskType: {node.task_type}, Effective Agent Name tried: {final_tried_name or 'None'})"
                logger.error(error_msg)
                node.update_status(TaskStatus.FAILED, error_msg=error_msg)
                return

            adapter_used_name = getattr(planner_adapter, 'agent_name', type(planner_adapter).__name__)
            logger.info(f"    ReadyPlanHandler: Using PLAN adapter '{adapter_used_name}' for node {node.task_id}")

            current_planner_input_model = resolve_input_for_planner_agent(
                current_task_id=node.task_id, knowledge_store=context.knowledge_store,
                overall_objective=current_overall_objective, planning_depth=node.layer,
                replan_details=None, global_constraints=getattr(context.task_graph, 'global_constraints', [])
            )
            node.input_payload_dict = current_planner_input_model.model_dump()
            plan_output: Optional[PlanOutput] = await planner_adapter.process(node, current_planner_input_model)

            if plan_output is None or not plan_output.sub_tasks:
                if node.status not in [TaskStatus.CANCELLED, TaskStatus.FAILED]:
                    logger.warning(f"    Node {node.task_id} (PLAN): Planner returned no sub-tasks or None.")
                    if plan_output is None:
                        node.update_status(TaskStatus.FAILED, error_msg="Planner failed to produce an output.")
                    else: 
                        logger.info(f"    Node {node.task_id} (PLAN): Planner returned an empty list. Interpreting as atomic.")
                        node.node_type = NodeType.EXECUTE
                        node.output_summary = "Planner determined no further sub-tasks are needed; task is atomic."
                        node.update_status(TaskStatus.PLAN_DONE) 
                return

            hitl_outcome_plan = await context.hitl_coordinator.review_plan_generation(
                node=node, plan_output=plan_output, planner_input=current_planner_input_model
            )

            if hitl_outcome_plan["status"] == "request_modification":
                logger.info(f"Node {node.task_id}: Plan modification requested. Setting to NEEDS_REPLAN.")
                modification_instructions = hitl_outcome_plan.get('modification_instructions', 'User requested modification.')
                node.replan_details = ReplanRequestDetails(
                    failed_sub_goal=node.goal, reason_for_failure_or_replan=modification_instructions,
                    specific_guidance_for_replan=modification_instructions
                )
                node.aux_data['original_plan_for_modification'] = plan_output 
                node.aux_data['user_modification_instructions'] = modification_instructions
                node.replan_reason = f"User requested modification: {modification_instructions[:100]}..."
                node.update_status(TaskStatus.NEEDS_REPLAN)
                node.output_summary = "Initial plan requires user modification."
                return
            elif hitl_outcome_plan["status"] != "approved":
                return 

            context.sub_node_creator.create_sub_nodes(node, plan_output)
            node.result = plan_output
            node.output_summary = f"Planned {len(plan_output.sub_tasks)} sub-tasks."
            node.update_status(TaskStatus.PLAN_DONE)
            logger.success(f"    ReadyPlanHandler: Node {node.task_id} planning complete. Status: {node.status.name}")

        finally:
            if node.agent_name != agent_name_at_entry:
                logger.debug(f"        ReadyPlanHandler: Restoring node.agent_name from '{node.agent_name}' to entry value '{agent_name_at_entry}' for node {node.task_id}")
                node.agent_name = agent_name_at_entry


class ReadyExecuteHandler(INodeHandler):
    """Handles a READY node that needs to be EXECUTED."""
    async def handle(self, node: TaskNode, context: ProcessorContext) -> None:
        agent_name_at_entry = node.agent_name
        blueprint_name_log = context.current_agent_blueprint.name if context.current_agent_blueprint else "N/A"
        logger.info(f"    ReadyExecuteHandler: Executing node {node.task_id} (Blueprint: {blueprint_name_log}, Goal: '{node.goal[:50]}...', Original Agent Name at Entry: {agent_name_at_entry})")

        try:
            context_builder_agent_name = agent_name_at_entry
            if context.current_agent_blueprint and node.task_type:
                specific_executor_name = context.current_agent_blueprint.executor_adapter_names.get(node.task_type)
                if specific_executor_name:
                    context_builder_agent_name = specific_executor_name
                elif not context_builder_agent_name and context.current_agent_blueprint.default_node_agent_name_prefix:
                    context_builder_agent_name = f"{context.current_agent_blueprint.default_node_agent_name_prefix}Executor"
            
            agent_task_input_model = resolve_context_for_agent(
                current_task_id=node.task_id, current_goal=node.goal,
                current_task_type=node.task_type.value if isinstance(node.task_type, TaskType) else str(node.task_type),
                knowledge_store=context.knowledge_store, agent_name=context_builder_agent_name or "default_executor",
                overall_project_goal=context.task_graph.overall_project_goal
            )
            node.input_payload_dict = agent_task_input_model.model_dump()

            hitl_outcome_exec = await context.hitl_coordinator.review_before_execution(
                node=node, agent_task_input=agent_task_input_model
            )
            if hitl_outcome_exec["status"] != "approved":
                return

            lookup_name_for_executor = agent_name_at_entry
            if context.current_agent_blueprint and node.task_type:
                specific_executor_name = context.current_agent_blueprint.executor_adapter_names.get(node.task_type)
                if specific_executor_name:
                    lookup_name_for_executor = specific_executor_name
                    logger.debug(f"        ReadyExecuteHandler: Blueprint specifies executor for {node.task_type}: {lookup_name_for_executor}")
                elif not lookup_name_for_executor and context.current_agent_blueprint.default_node_agent_name_prefix:
                    lookup_name_for_executor = f"{context.current_agent_blueprint.default_node_agent_name_prefix}Executor"
                    logger.debug(f"        ReadyExecuteHandler: Blueprint suggests prefix for executor: {lookup_name_for_executor}")

            node.agent_name = lookup_name_for_executor 
            executor_adapter = get_agent_adapter(node, action_verb="execute")

            if not executor_adapter and agent_name_at_entry and node.agent_name != agent_name_at_entry:
                logger.debug(f"        ReadyExecuteHandler: Blueprint executor lookup failed for {node.task_type}. Trying original entry agent_name: {agent_name_at_entry}")
                node.agent_name = agent_name_at_entry
                executor_adapter = get_agent_adapter(node, action_verb="execute")

            if not executor_adapter:
                final_tried_name = node.agent_name or lookup_name_for_executor or agent_name_at_entry
                error_msg = f"No EXECUTE adapter found for node {node.task_id} (TaskType: {node.task_type}, NodeType: {node.node_type}, Effective Agent Name tried: {final_tried_name or 'None'})"
                logger.error(error_msg)
                node.update_status(TaskStatus.FAILED, error_msg=error_msg)
                return
            
            adapter_used_name = getattr(executor_adapter, 'agent_name', type(executor_adapter).__name__)
            logger.info(f"    ReadyExecuteHandler: Calling executor adapter '{adapter_used_name}' for node {node.task_id}")

            execution_result: Optional[Any] = await executor_adapter.process(node, agent_task_input_model)

            if execution_result is not None:
                node.result = execution_result
                if isinstance(execution_result, BaseModel):
                    try:
                        if hasattr(execution_result, 'summary') and execution_result.summary: 
                            node.output_summary = str(execution_result.summary) 
                        elif hasattr(execution_result, 'content_summary') and execution_result.content_summary: 
                            node.output_summary = str(execution_result.content_summary)
                        elif isinstance(execution_result, CustomSearcherOutput):
                            summary_text = str(execution_result)[:100] + "..." if len(str(execution_result)) > 100 else str(execution_result)
                            annotation_count = len(execution_result.annotations) if execution_result.annotations else 0
                            node.output_summary = f"Search result: \"{summary_text}\" ({annotation_count} annotations)"
                        elif isinstance(execution_result, PlanOutput): 
                            node.output_summary = f"Plan output from executor: {len(execution_result.sub_tasks)} sub-tasks."
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
        finally:
            if node.agent_name != agent_name_at_entry:
                logger.debug(f"        ReadyExecuteHandler: Restoring node.agent_name from '{node.agent_name}' to entry value '{agent_name_at_entry}' for node {node.task_id}")
                node.agent_name = agent_name_at_entry


class ReadyNodeHandler(INodeHandler):
    """Handles a node in READY status, determining if it needs atomization, planning, or execution."""
    def __init__(self, ready_plan_handler: ReadyPlanHandler, ready_execute_handler: ReadyExecuteHandler):
        self.ready_plan_handler = ready_plan_handler
        self.ready_execute_handler = ready_execute_handler

    async def handle(self, node: TaskNode, context: ProcessorContext) -> None:
        logger.info(f"  ReadyNodeHandler: Handling READY node {node.task_id} (Original NodeType: {node.node_type}, Goal: '{node.goal[:30]}...')")
        node.update_status(TaskStatus.RUNNING)
        
        action_to_take_after_atomizer = await context.node_atomizer.atomize_node(node, context)

        if action_to_take_after_atomizer is None: 
            logger.info(f"Node {node.task_id} processing halted after atomizer/HITL attempt (atomizer returned None). Current node status: {node.status}")
            return

        current_node_type_value = node.node_type 
        if isinstance(current_node_type_value, str):
            try:
                node.node_type = NodeType[current_node_type_value.upper()] 
                logger.debug(f"    ReadyNodeHandler: Coerced node.node_type from string '{current_node_type_value}' to enum {node.node_type}")
            except KeyError:
                logger.error(f"    ReadyNodeHandler: Invalid string value '{current_node_type_value}' for node.node_type. Cannot convert. Node {node.task_id} will fail.")
                node.update_status(TaskStatus.FAILED, error_msg=f"Invalid node.node_type string: {current_node_type_value}")
                return
        elif not isinstance(current_node_type_value, NodeType):
             logger.warning(f"    ReadyNodeHandler: node.node_type for {node.task_id} is not string or NodeType: {type(current_node_type_value)}. Using atomizer's suggestion.")
             if isinstance(action_to_take_after_atomizer, NodeType): 
                 node.node_type = action_to_take_after_atomizer
                 logger.info(f"    Set node.node_type to atomizer's suggestion: {node.node_type}")
             else: 
                 logger.error(f"    Atomizer's suggestion is also not a NodeType enum: {type(action_to_take_after_atomizer)}. Failing node {node.task_id}.")
                 node.update_status(TaskStatus.FAILED, error_msg=f"Invalid node.node_type {type(current_node_type_value)} and atomizer suggestion {type(action_to_take_after_atomizer)}")
                 return
        
        if node.node_type == NodeType.PLAN and node.layer >= context.config.max_planning_layer:
            logger.warning(f"    ReadyNodeHandler: Max planning depth ({context.config.max_planning_layer}) reached for {node.task_id}. Forcing EXECUTE.")
            node.node_type = NodeType.EXECUTE 
        
        current_action_type = node.node_type 

        if current_action_type == NodeType.PLAN:
            await self.ready_plan_handler.handle(node, context)
        elif current_action_type == NodeType.EXECUTE:
            await self.ready_execute_handler.handle(node, context)
        else:
            logger.error(f"Node {node.task_id}: Unhandled or invalid NodeType '{current_action_type}' (type: {type(current_action_type)}) in ReadyNodeHandler. Expected NodeType.PLAN or NodeType.EXECUTE.")
            node.update_status(TaskStatus.FAILED, error_msg=f"Unhandled or invalid NodeType '{current_action_type}' for READY node.")


class AggregatingNodeHandler(INodeHandler):
    """Handles a node in AGGREGATING status."""
    async def handle(self, node: TaskNode, context: ProcessorContext) -> None:
        agent_name_at_entry = node.agent_name
        blueprint_name_log = context.current_agent_blueprint.name if context.current_agent_blueprint else "N/A"
        logger.info(f"  AggregatingNodeHandler: Handling AGGREGATING node {node.task_id} (Blueprint: {blueprint_name_log}, Goal: '{node.goal[:30]}...', Original Agent Name at Entry: {agent_name_at_entry})")
        
        try:
            node.update_status(TaskStatus.RUNNING)
            child_results_for_aggregator: list = [] 
            if node.sub_graph_id:
                child_nodes = context.task_graph.get_nodes_in_graph(node.sub_graph_id)
                for child_node in child_nodes:
                    child_status = child_node.status if isinstance(child_node.status, TaskStatus) else TaskStatus(str(child_node.status))
                    if child_status in [TaskStatus.DONE, TaskStatus.FAILED]:
                        child_results_for_aggregator.append(ContextItem( 
                            source_task_id=child_node.task_id, source_task_goal=child_node.goal,
                            content=child_node.result if child_status == TaskStatus.DONE else child_node.error,
                            content_type_description=f"child_{child_status.value.lower()}_output"
                        ))

            context_builder_agent_name = agent_name_at_entry
            if context.current_agent_blueprint and context.current_agent_blueprint.aggregator_adapter_name:
                context_builder_agent_name = context.current_agent_blueprint.aggregator_adapter_name
            elif not context_builder_agent_name and context.current_agent_blueprint and context.current_agent_blueprint.default_node_agent_name_prefix:
                context_builder_agent_name = f"{context.current_agent_blueprint.default_node_agent_name_prefix}Aggregator"

            agent_task_input = AgentTaskInput(
                current_task_id=node.task_id, current_goal=node.goal,
                current_task_type=TaskType.AGGREGATE.value, relevant_context_items=child_results_for_aggregator, 
                overall_project_goal=context.task_graph.overall_project_goal
            )
            node.input_payload_dict = agent_task_input.model_dump()

            if not isinstance(node.node_type, NodeType): 
                node.node_type = NodeType(str(node.node_type)) 

            lookup_name_for_aggregator = agent_name_at_entry
            if context.current_agent_blueprint and context.current_agent_blueprint.aggregator_adapter_name:
                lookup_name_for_aggregator = context.current_agent_blueprint.aggregator_adapter_name
                logger.debug(f"        AggregatingNodeHandler: Blueprint specifies aggregator: {lookup_name_for_aggregator}")
            elif not lookup_name_for_aggregator and context.current_agent_blueprint and context.current_agent_blueprint.default_node_agent_name_prefix:
                lookup_name_for_aggregator = f"{context.current_agent_blueprint.default_node_agent_name_prefix}Aggregator"
                logger.debug(f"        AggregatingNodeHandler: Blueprint suggests prefix for aggregator: {lookup_name_for_aggregator}")

            node.agent_name = lookup_name_for_aggregator
            aggregator_adapter = get_agent_adapter(node, action_verb="aggregate")

            if not aggregator_adapter and agent_name_at_entry and node.agent_name != agent_name_at_entry:
                logger.debug(f"        AggregatingNodeHandler: Blueprint aggregator lookup failed. Trying original entry agent_name: {agent_name_at_entry}")
                node.agent_name = agent_name_at_entry
                aggregator_adapter = get_agent_adapter(node, action_verb="aggregate")

            if not aggregator_adapter:
                final_tried_name = node.agent_name or lookup_name_for_aggregator or agent_name_at_entry
                error_msg = f"No AGGREGATE adapter found for node {node.task_id} (Effective Agent Name tried: {final_tried_name or 'None'})"
                logger.error(error_msg)
                node.update_status(TaskStatus.FAILED, error_msg=error_msg)
                return

            adapter_used_name = getattr(aggregator_adapter, 'agent_name', type(aggregator_adapter).__name__)
            logger.info(f"    AggregatingNodeHandler: Invoking AGGREGATE adapter '{adapter_used_name}' for {node.task_id}")

            aggregated_result = await aggregator_adapter.process(node, agent_task_input)
            node.output_type_description = "aggregated_text_result"
            node.update_status(TaskStatus.DONE, result=aggregated_result)
            logger.success(f"    AggregatingNodeHandler: Node {node.task_id} aggregation complete. Status: {node.status.name}.")
        finally:
            if node.agent_name != agent_name_at_entry:
                logger.debug(f"        AggregatingNodeHandler: Restoring node.agent_name from '{node.agent_name}' to entry value '{agent_name_at_entry}' for node {node.task_id}")
                node.agent_name = agent_name_at_entry


class NeedsReplanNodeHandler(INodeHandler):
    """Handles a node in NEEDS_REPLAN status."""
    async def handle(self, node: TaskNode, context: ProcessorContext) -> None:
        agent_name_at_entry = node.agent_name
        blueprint_name_log = context.current_agent_blueprint.name if context.current_agent_blueprint else "N/A"
        logger.info(f"  NeedsReplanNodeHandler: Handling NEEDS_REPLAN node {node.task_id} (Blueprint: {blueprint_name_log}, Replan Attempts: {node.replan_attempts}, Goal: '{node.goal[:30]}...', Original Agent Name at Entry: {agent_name_at_entry})")

        try:
            # Check if this is a user-requested modification
            is_user_modification = node.aux_data.get('user_modification_instructions') is not None
            
            # Only check max attempts for system-triggered replans, not user modifications
            if not is_user_modification and node.replan_attempts >= context.config.max_replan_attempts:
                logger.warning(f"    Node {node.task_id}: Max replan attempts ({context.config.max_replan_attempts}) reached. Marking as FAILED.")
                node.update_status(TaskStatus.FAILED, error_msg="Max replan attempts reached.")
                return

            # Only increment replan_attempts for system-triggered replans
            if not is_user_modification:
                node.replan_attempts += 1 
            
            node.update_status(TaskStatus.RUNNING)
            node.node_type = NodeType.PLAN 

            current_overall_objective = node.overall_objective or getattr(context.task_graph, 'overall_project_goal', "Undefined overall project goal")
            
            active_adapter = None
            is_modifier_agent = False 
            action_verb_to_use = "modify_plan"
            lookup_name_for_replan_op = agent_name_at_entry 

            if context.current_agent_blueprint:
                if context.current_agent_blueprint.plan_modifier_adapter_name:
                    lookup_name_for_replan_op = context.current_agent_blueprint.plan_modifier_adapter_name
                    logger.debug(f"        NeedsReplan: Blueprint specifies plan_modifier: {lookup_name_for_replan_op}")
                elif not lookup_name_for_replan_op and context.current_agent_blueprint.default_node_agent_name_prefix:
                    lookup_name_for_replan_op = f"{context.current_agent_blueprint.default_node_agent_name_prefix}PlanModifier"
                    logger.debug(f"        NeedsReplan: Blueprint suggests prefix for plan_modifier: {lookup_name_for_replan_op}")
            
            node.agent_name = lookup_name_for_replan_op
            active_adapter = get_agent_adapter(node, action_verb=action_verb_to_use)
            if active_adapter: is_modifier_agent = True

            if not active_adapter: 
                logger.warning(f"    NeedsReplan: No '{action_verb_to_use}' adapter resolved (tried: {node.agent_name}). Falling back to 'plan' adapter.")
                action_verb_to_use = "plan"
                is_modifier_agent = False
                lookup_name_for_replan_op = agent_name_at_entry 

                if context.current_agent_blueprint:
                    if context.current_agent_blueprint.planner_adapter_name:
                        lookup_name_for_replan_op = context.current_agent_blueprint.planner_adapter_name
                        logger.debug(f"        NeedsReplan: Blueprint specifies planner for replan: {lookup_name_for_replan_op}")
                    elif not lookup_name_for_replan_op and context.current_agent_blueprint.default_node_agent_name_prefix:
                         lookup_name_for_replan_op = f"{context.current_agent_blueprint.default_node_agent_name_prefix}Planner"
                         logger.debug(f"        NeedsReplan: Blueprint suggests prefix for planner (replan): {lookup_name_for_replan_op}")
                
                node.agent_name = lookup_name_for_replan_op
                active_adapter = get_agent_adapter(node, action_verb=action_verb_to_use)

            if not active_adapter and agent_name_at_entry and node.agent_name != agent_name_at_entry:
                logger.debug(f"        NeedsReplan: Blueprint lookups failed. Trying original entry agent_name: {agent_name_at_entry} with verb {action_verb_to_use}")
                node.agent_name = agent_name_at_entry
                active_adapter = get_agent_adapter(node, action_verb=action_verb_to_use)
                if action_verb_to_use == "modify_plan" and active_adapter: is_modifier_agent = True # Re-check if original was modifier

            if not active_adapter:
                final_tried_name = node.agent_name or lookup_name_for_replan_op or agent_name_at_entry
                error_msg = f"No suitable PLAN or MODIFY_PLAN adapter found for node {node.task_id} for replanning (Effective Agent Name tried: {final_tried_name or 'None'})"
                logger.error(error_msg)
                node.update_status(TaskStatus.FAILED, error_msg=error_msg)
                return

            adapter_used_name = getattr(active_adapter, 'agent_name', type(active_adapter).__name__)
            logger.info(f"    NeedsReplanNodeHandler: Using {'PlanModifier' if is_modifier_agent else 'Plan'} adapter '{adapter_used_name}' for replan of node {node.task_id}")

            input_for_replan: Any
            if is_modifier_agent:
                original_plan = node.aux_data.get('original_plan_for_modification')
                user_instructions = node.aux_data.get('user_modification_instructions')
                if isinstance(original_plan, PlanOutput) and user_instructions:
                    input_for_replan = PlanModifierInput(
                        overall_objective=current_overall_objective, original_plan=original_plan,
                        user_modification_instructions=user_instructions, replan_request_details=node.replan_details
                    )
                else: 
                    logger.warning(f"Node {node.task_id}: Missing data for PlanModifier. Falling back to standard planner for replan.")
                    action_verb_to_use = "plan"; is_modifier_agent = False
                    lookup_name_for_replan_op = agent_name_at_entry 
                    if context.current_agent_blueprint and context.current_agent_blueprint.planner_adapter_name:
                        lookup_name_for_replan_op = context.current_agent_blueprint.planner_adapter_name
                    node.agent_name = lookup_name_for_replan_op # Set for planner lookup
                    active_adapter = get_agent_adapter(node, action_verb=action_verb_to_use) # Re-fetch adapter
                    
                    if not active_adapter and agent_name_at_entry and node.agent_name != agent_name_at_entry : 
                        node.agent_name = agent_name_at_entry
                        active_adapter = get_agent_adapter(node, action_verb=action_verb_to_use)

                    if not active_adapter: # Still no planner? Fail.
                        node.update_status(TaskStatus.FAILED, error_msg="Fallback to Plan adapter failed during replan due to missing PlanModifier inputs & subsequent planner lookup failure.")
                        return
                    logger.info(f"    NeedsReplanNodeHandler: Switched to Plan adapter '{getattr(active_adapter, 'agent_name', type(active_adapter).__name__)}' for replan.")
                    input_for_replan = resolve_input_for_planner_agent(
                        current_task_id=node.task_id, knowledge_store=context.knowledge_store,
                        overall_objective=current_overall_objective, planning_depth=node.layer,
                        replan_details=node.replan_details, global_constraints=getattr(context.task_graph, 'global_constraints', [])
                    )
            else: 
                input_for_replan = resolve_input_for_planner_agent(
                    current_task_id=node.task_id, knowledge_store=context.knowledge_store,
                    overall_objective=current_overall_objective, planning_depth=node.layer,
                    replan_details=node.replan_details, global_constraints=getattr(context.task_graph, 'global_constraints', [])
                )
            node.input_payload_dict = input_for_replan.model_dump()
            new_plan_output: Optional[PlanOutput] = await active_adapter.process(node, input_for_replan)

            if new_plan_output is None or not new_plan_output.sub_tasks:
                logger.warning(f"    Node {node.task_id} (NEEDS_REPLAN): {'PlanModifier' if is_modifier_agent else 'Planner'} returned no sub-tasks.")
                node.update_status(TaskStatus.FAILED, error_msg=f"{'PlanModifier' if is_modifier_agent else 'Planner'} failed to produce new plan.")
                return

            # Check if this replan was triggered by user modification
            is_user_modification = node.aux_data.get('user_modification_instructions') is not None

            if is_user_modification:
                # Use review_modified_plan for user-requested modifications
                hitl_outcome_replan = await context.hitl_coordinator.review_modified_plan(
                    node=node, modified_plan=new_plan_output, replan_attempt_count=node.replan_attempts
                )
            else:
                # Use review_plan_generation for system-triggered replans
                hitl_outcome_replan = await context.hitl_coordinator.review_plan_generation(
                    node=node, plan_output=new_plan_output,
                    planner_input=input_for_replan, is_replan=True 
                )

            if hitl_outcome_replan["status"] == "approved":
                # Plan approved, proceed with applying the plan
                pass
            elif hitl_outcome_replan["status"] == "request_modification":
                # User requested another modification - update the node for another replan cycle
                logger.info(f"Node {node.task_id}: User requested another modification.")
                modification_instructions = hitl_outcome_replan.get('modification_instructions', 'User requested modification.')
                
                # Update the node for another modification cycle
                node.aux_data['original_plan_for_modification'] = new_plan_output
                node.aux_data['user_modification_instructions'] = modification_instructions
                node.replan_reason = f"User requested modification: {modification_instructions[:100]}..."
                node.update_status(TaskStatus.NEEDS_REPLAN)
                node.output_summary = "Plan requires user modification."
                return
            else:
                # Handle other statuses (aborted, error, etc.)
                logger.info(f"Node {node.task_id}: Replan not approved by user. Status: {hitl_outcome_replan['status']}")
                if node.status not in [TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.NEEDS_REPLAN]:
                     node.update_status(TaskStatus.FAILED, error_msg="Replanning not approved by user.")
                return

            if node.sub_graph_id: 
                logger.info(f"    Node {node.task_id}: Clearing existing sub-graph {node.sub_graph_id} before applying new plan.")
                context.task_graph.remove_graph_and_nodes(node.sub_graph_id) 
                node.sub_graph_id = None
                node.planned_sub_task_ids = [] 
            
            context.sub_node_creator.create_sub_nodes(node, new_plan_output)
            node.result = new_plan_output
            node.output_summary = f"Replanned with {len(new_plan_output.sub_tasks)} sub-tasks after {node.replan_attempts} attempt(s)."
            node.replan_details = None 
            node.aux_data.pop('original_plan_for_modification', None) 
            node.aux_data.pop('user_modification_instructions', None)
            node.replan_reason = None 
            node.update_status(TaskStatus.PLAN_DONE) 
            logger.success(f"    NeedsReplanNodeHandler: Node {node.task_id} replanning complete. Status: {node.status.name}")
        finally:
            if node.agent_name != agent_name_at_entry:
                logger.debug(f"        NeedsReplanNodeHandler: Restoring node.agent_name from '{node.agent_name}' to entry value '{agent_name_at_entry}' for node {node.task_id}")
                node.agent_name = agent_name_at_entry