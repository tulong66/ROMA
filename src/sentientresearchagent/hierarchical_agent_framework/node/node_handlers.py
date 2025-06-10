from typing import Optional, Any, cast
from loguru import logger

from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskStatus, NodeType, TaskType
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import (
    AgentTaskInput, PlanOutput, ReplanRequestDetails, CustomSearcherOutput, PlanModifierInput, ContextItem
)
from sentientresearchagent.hierarchical_agent_framework.context.context_builder import (
    resolve_context_for_agent,
)
from sentientresearchagent.hierarchical_agent_framework.context.planner_context_builder import resolve_input_for_planner_agent
from pydantic import BaseModel

from .inode_handler import INodeHandler, ProcessorContext
from ..context.enhanced_context_builder import resolve_context_for_agent_with_parents
from ..context.smart_context_utils import get_smart_child_context


def get_planner_from_blueprint(blueprint: 'AgentBlueprint', task_type: TaskType, fallback_name: Optional[str] = None, node: Optional[TaskNode] = None) -> Optional[str]:
    """
    Get the appropriate planner name from blueprint based on task type and node level.
    
    Args:
        blueprint: The agent blueprint
        task_type: The task type needing planning
        fallback_name: Fallback agent name if blueprint doesn't specify
        node: The TaskNode (needed to determine if it's root)
        
    Returns:
        Agent name to use for planning, or None if no suitable planner found
    """
    if not blueprint:
        return fallback_name
    
    # NEW: Check if this is the root node and if blueprint has root planner
    if node:
        is_root_node = (
            node.task_id == "root" or 
            getattr(node, 'layer', 0) == 0 or
            getattr(node, 'parent_node_id', None) is None
        )
        
        if is_root_node and hasattr(blueprint, 'root_planner_adapter_name') and blueprint.root_planner_adapter_name:
            planner_name = blueprint.root_planner_adapter_name
            logger.info(f"🎯 Using ROOT planner for root node {node.task_id}: {planner_name}")
            return planner_name
        else:
            logger.info(f"📋 Using task-specific planner for non-root node {node.task_id} (layer: {getattr(node, 'layer', 'unknown')}, parent: {getattr(node, 'parent_node_id', 'unknown')})")
    
    # 1. Try task-specific planner
    if hasattr(blueprint, 'planner_adapter_names') and task_type in blueprint.planner_adapter_names:
        planner_name = blueprint.planner_adapter_names[task_type]
        logger.debug(f"Blueprint specifies planner for {task_type}: {planner_name}")
        return planner_name
    
    # 2. Try default planner
    if hasattr(blueprint, 'default_planner_adapter_name') and blueprint.default_planner_adapter_name:
        planner_name = blueprint.default_planner_adapter_name
        logger.debug(f"Blueprint specifies default planner: {planner_name}")
        return planner_name
    
    # 3. Try legacy single planner (backward compatibility)
    if hasattr(blueprint, 'planner_adapter_name') and blueprint.planner_adapter_name:
        planner_name = blueprint.planner_adapter_name
        logger.debug(f"Blueprint specifies legacy single planner: {planner_name}")
        return planner_name
    
    # 4. Try prefix-based naming
    if hasattr(blueprint, 'default_node_agent_name_prefix') and blueprint.default_node_agent_name_prefix:
        planner_name = f"{blueprint.default_node_agent_name_prefix}Planner"
        logger.debug(f"Blueprint suggests prefix-based planner: {planner_name}")
        return planner_name
    
    return fallback_name


def get_executor_from_blueprint(blueprint: 'AgentBlueprint', task_type: TaskType, fallback_name: Optional[str] = None) -> Optional[str]:
    """
    Get the appropriate executor name from blueprint based on task type.
    
    Args:
        blueprint: The agent blueprint
        task_type: The task type needing execution
        fallback_name: Fallback agent name if blueprint doesn't specify
        
    Returns:
        Agent name to use for execution, or None if no suitable executor found
    """
    if not blueprint:
        return fallback_name
    
    # 1. Try task-specific executor
    if hasattr(blueprint, 'executor_adapter_names') and task_type in blueprint.executor_adapter_names:
        executor_name = blueprint.executor_adapter_names[task_type]
        logger.debug(f"Blueprint specifies executor for {task_type}: {executor_name}")
        return executor_name
    
    # 2. Try default executor
    if hasattr(blueprint, 'default_executor_adapter_name') and blueprint.default_executor_adapter_name:
        executor_name = blueprint.default_executor_adapter_name
        logger.debug(f"Blueprint specifies default executor: {executor_name}")
        return executor_name
    
    # 3. Try prefix-based naming
    if hasattr(blueprint, 'default_node_agent_name_prefix') and blueprint.default_node_agent_name_prefix:
        executor_name = f"{blueprint.default_node_agent_name_prefix}Executor"
        logger.debug(f"Blueprint suggests prefix-based executor: {executor_name}")
        return executor_name
    
    return fallback_name


class ReadyPlanHandler(INodeHandler):
    """Handles a READY node that needs to be PLANNED."""
    async def handle(self, node: TaskNode, context: ProcessorContext) -> None:
        agent_name_at_entry = node.agent_name
        blueprint_name_log = context.current_agent_blueprint.name if context.current_agent_blueprint else "N/A"
        logger.info(f"    ReadyPlanHandler: Planning for node {node.task_id} (Blueprint: {blueprint_name_log}, Goal: '{node.goal[:50]}...', Original Agent Name at Entry: {agent_name_at_entry})")
        
        try:
            current_overall_objective = node.overall_objective or getattr(context.task_graph, 'overall_project_goal', "Undefined overall project goal")
            
            # ENHANCED: Use new blueprint system for planner selection with node parameter
            lookup_name_for_planner = get_planner_from_blueprint(
                context.current_agent_blueprint, 
                node.task_type, 
                agent_name_at_entry,
                node  # NEW: Pass the node so we can check if it's root
            )

            node.agent_name = lookup_name_for_planner 
            planner_adapter = context.agent_registry.get_agent_adapter(node, action_verb="plan")

            if not planner_adapter and agent_name_at_entry and node.agent_name != agent_name_at_entry:
                logger.debug(f"        ReadyPlanHandler: Blueprint planner lookup failed. Trying original entry agent_name for plan: {agent_name_at_entry}")
                node.agent_name = agent_name_at_entry
                planner_adapter = context.agent_registry.get_agent_adapter(node, action_verb="plan")
            
            if not planner_adapter:
                final_tried_name = node.agent_name or lookup_name_for_planner or agent_name_at_entry
                error_msg = f"No PLAN adapter found for node {node.task_id} (TaskType: {node.task_type}, Effective Agent Name tried: {final_tried_name or 'None'})"
                logger.error(error_msg)
                node.update_status(TaskStatus.FAILED, error_msg=error_msg)
                return

            adapter_used_name = getattr(planner_adapter, 'agent_name', type(planner_adapter).__name__)
            logger.info(f"    ReadyPlanHandler: Using PLAN adapter '{adapter_used_name}' for node {node.task_id}")

            # ENHANCED: Use blueprint for context builder agent selection too
            context_builder_agent_name = get_executor_from_blueprint(
                context.current_agent_blueprint,
                node.task_type,
                agent_name_at_entry
            )
            
            agent_task_input_model = resolve_context_for_agent_with_parents(
                current_task_id=node.task_id,
                current_goal=node.goal,
                current_task_type=node.task_type.value,
                knowledge_store=context.knowledge_store,
                agent_name=context_builder_agent_name,
                overall_project_goal=context.task_graph.overall_project_goal
            )
            formatted_context = agent_task_input_model.formatted_full_context
            node.input_payload_dict = agent_task_input_model.model_dump()
            
            plan_output: Optional[PlanOutput] = await planner_adapter.process(node, agent_task_input_model)

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
                node=node, plan_output=plan_output, planner_input=agent_task_input_model
            )
            if hitl_outcome_plan["status"] == "request_modification":
                # User requested modification - set up node for replan
                modification_instructions = hitl_outcome_plan.get('modification_instructions', 'User requested modification.')
                
                # Set up auxiliary data for the modification
                node.aux_data['original_plan_for_modification'] = plan_output
                node.aux_data['user_modification_instructions'] = modification_instructions
                node.replan_reason = f"User requested modification: {modification_instructions[:100]}..."
                
                # Transition to NEEDS_REPLAN status
                node.update_status(TaskStatus.NEEDS_REPLAN)
                node.output_summary = "Plan requires user modification."
                
                # Update knowledge store to persist the status change
                context.knowledge_store.add_or_update_record_from_node(node)
                logger.info(f"✅ Node {node.task_id} set up for modification and transitioned to NEEDS_REPLAN")
                return
            elif hitl_outcome_plan["status"] != "approved":
                # Handle other non-approved statuses (aborted, error, etc.)
                return

            if node.layer + 1 >= context.config.max_planning_layer:
                logger.warning(f"    ReadyPlanHandler: Creating sub-nodes for {node.task_id} at layer {node.layer} would exceed max planning depth ({context.config.max_planning_layer}). Converting to atomic execution task.")
                node.node_type = NodeType.EXECUTE
                node.result = plan_output
                node.output_summary = f"Plan created but converted to atomic task due to max depth limit. Contains {len(plan_output.sub_tasks)} potential sub-tasks."
                node.update_status(TaskStatus.READY)
                logger.info(f"    ReadyPlanHandler: Node {node.task_id} converted to atomic execution task due to depth limit and set to READY for execution.")
                return
            else:
                logger.debug(f"    ReadyPlanHandler: Depth check passed for {node.task_id}, proceeding to create {len(plan_output.sub_tasks)} sub-nodes")

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
            # ENHANCED: Use blueprint for context builder agent selection
            context_builder_agent_name = get_executor_from_blueprint(
                context.current_agent_blueprint,
                node.task_type,
                agent_name_at_entry or "default_executor"
            )
            
            agent_task_input_model = resolve_context_for_agent_with_parents(
                current_task_id=node.task_id, 
                current_goal=node.goal,
                current_task_type=node.task_type.value if isinstance(node.task_type, TaskType) else str(node.task_type),
                knowledge_store=context.knowledge_store, 
                agent_name=context_builder_agent_name,
                overall_project_goal=context.task_graph.overall_project_goal
            )
            node.input_payload_dict = agent_task_input_model.model_dump()

            hitl_outcome_exec = await context.hitl_coordinator.review_before_execution(
                node=node, agent_task_input=agent_task_input_model
            )
            if hitl_outcome_exec["status"] != "approved":
                return

            # ENHANCED: Use new blueprint system for executor selection
            lookup_name_for_executor = get_executor_from_blueprint(
                context.current_agent_blueprint,
                node.task_type,
                agent_name_at_entry
            )

            node.agent_name = lookup_name_for_executor 
            executor_adapter = context.agent_registry.get_agent_adapter(node, action_verb="execute")

            if not executor_adapter and agent_name_at_entry and node.agent_name != agent_name_at_entry:
                logger.debug(f"        ReadyExecuteHandler: Blueprint executor lookup failed for {node.task_type}. Trying original entry agent_name: {agent_name_at_entry}")
                node.agent_name = agent_name_at_entry
                executor_adapter = context.agent_registry.get_agent_adapter(node, action_verb="execute")

            if not executor_adapter:
                final_tried_name = node.agent_name or lookup_name_for_executor or agent_name_at_entry
                error_msg = f"No EXECUTE adapter found for node {node.task_id} (TaskType: {node.task_type}, NodeType: {node.node_type}, Effective Agent Name tried: {final_tried_name or 'None'})"
                logger.error(error_msg)
                node.update_status(TaskStatus.FAILED, error_msg=error_msg)
                return
            
            adapter_used_name = getattr(executor_adapter, 'agent_name', type(executor_adapter).__name__)
            logger.info(f"    ReadyExecuteHandler: Using EXECUTE adapter '{adapter_used_name}' for node {node.task_id}")

            node.update_status(TaskStatus.RUNNING)
            execution_result = await executor_adapter.process(node, agent_task_input_model)

            if execution_result is not None:
                node.result = execution_result
                if hasattr(execution_result, 'model_dump'):
                    node.output_summary = f"Execution completed. Structured output stored."
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
        logger.info(f"  ReadyNodeHandler: Handling READY node {node.task_id} (Initial NodeType: {node.node_type}, Layer: {node.layer}, Goal: '{node.goal[:30]}...')")
        node.update_status(TaskStatus.RUNNING) # Set status to RUNNING early

        # Use the max_planning_layer from the NodeProcessorConfig
        # This layer defines the threshold related to planning depth.
        # A node at layer L, if it's a PLAN node, its children would be at L+1.
        # ReadyPlanHandler converts a node at layer L to EXECUTE if (L+1) >= max_planning_layer.
        # This means a node at (max_planning_layer - 1) will be converted to EXECUTE by ReadyPlanHandler.
        max_planning_layer = context.config.max_planning_layer
        
        # --- Pre-Atomizer Depth Checks ---

        # 1. If the node itself is at a layer where it absolutely cannot be a PLAN node
        #    whose children would be within valid depth (i.e., node.layer >= max_planning_layer),
        #    force it to EXECUTE and skip atomization.
        #    (e.g. if max_planning_layer = 5, nodes at layer 5 or deeper are forced EXECUTE here)
        if node.layer >= max_planning_layer:
            logger.warning(
                f"    ReadyNodeHandler: Node {node.task_id} (Layer {node.layer}) is at or exceeds max_planning_layer "
                f"({max_planning_layer}). Forcing to EXECUTE. Atomizer is skipped."
            )
            node.node_type = NodeType.EXECUTE
            await self.ready_execute_handler.handle(node, context)
            return

        # At this point: node.layer < max_planning_layer.
        # This means the node *could* potentially be a PLAN node based on its own depth.

        # --- Run Atomizer ---
        # Atomizer runs for nodes that are not yet at the absolute max depth for planning.
        logger.info(f"    ReadyNodeHandler: Node {node.task_id} (Layer {node.layer}, Initial NodeType: {node.node_type}) "
                    f"proceeding to atomization (layer < {max_planning_layer}).")
        
        atomizer_decision_type: Optional[NodeType] = None
        try:
            atomizer_decision_type = await context.node_atomizer.atomize_node(node, context)
            
            if atomizer_decision_type is None:
                raise ValueError("Atomizer returned None NodeType, which is unexpected.")
            
            logger.info(f"    ReadyNodeHandler: Atomizer for node {node.task_id} determined NodeType: {atomizer_decision_type}")

        except Exception as e:
            logger.exception(f"    ReadyNodeHandler: Error during atomization for node {node.task_id}. Marking FAILED.")
            node.update_status(TaskStatus.FAILED, error_msg=f"Error during node atomization: {str(e)}")
            return # Stop processing if atomization itself fails

        # --- Post-Atomizer Decision Logic ---
        final_node_type = atomizer_decision_type

        # 2. Critical Depth Constraint for Atomizer's PLAN decision:
        # If the atomizer suggests PLAN, but the node is at the layer (max_planning_layer - 1),
        # it would be converted to EXECUTE by ReadyPlanHandler (because its children would be at max_planning_layer).
        # This would lead to the infinite loop if ReadyPlanHandler sets status to READY.
        # So, we override the atomizer's PLAN decision to EXECUTE here to prevent the loop.
        # (e.g. if max_planning_layer = 5, nodes at layer 4 decided PLAN by atomizer are forced EXECUTE here)
        if atomizer_decision_type == NodeType.PLAN and node.layer == (max_planning_layer - 1):
            logger.warning(
                f"    ReadyNodeHandler: Node {node.task_id} (Layer {node.layer}) determined PLAN by atomizer, "
                f"but is at critical depth (max_planning_layer - 1 = {max_planning_layer - 1}). "
                f"Overriding to EXECUTE to prevent planning loop."
            )
            final_node_type = NodeType.EXECUTE
        
        # --- Dispatch Based on Final Determined Node Type ---
        node.node_type = final_node_type # Set the node's type definitively

        if node.node_type == NodeType.PLAN:
            # This implies node.layer < (max_planning_layer - 1).
            # ReadyPlanHandler can create sub-nodes without this parent node being forced back into a loop-inducing state.
            logger.info(f"    ReadyNodeHandler: Node {node.task_id} is NodeType.PLAN. Calling ready_plan_handler.")
            await self.ready_plan_handler.handle(node, context)
        elif node.node_type == NodeType.EXECUTE:
            logger.info(f"    ReadyNodeHandler: Node {node.task_id} is NodeType.EXECUTE. Calling ready_execute_handler.")
            await self.ready_execute_handler.handle(node, context)
        else:
            logger.error(
                f"    ReadyNodeHandler: Node {node.task_id} has an unexpected final NodeType '{node.node_type}' "
                f"after atomization and depth checks. Expected NodeType.PLAN or NodeType.EXECUTE."
            )
            node.update_status(TaskStatus.FAILED, error_msg=f"Node has unhandled final NodeType: {node.node_type}")


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
                total_child_content_size = 0
                
                for child_node in child_nodes:
                    child_status = child_node.status if isinstance(child_node.status, TaskStatus) else TaskStatus(str(child_node.status))
                    
                    if child_status in [TaskStatus.DONE, TaskStatus.FAILED]:
                        child_content = child_node.result if child_status == TaskStatus.DONE else child_node.error
                        
                        # 🔥 NEW: Use smart context sizing
                        processed_content, processing_method = get_smart_child_context(
                            content=child_content,
                            child_task_goal=child_node.goal,
                            child_task_type=child_node.task_type or "UNKNOWN"
                        )
                        
                        total_child_content_size += len(processed_content)
                        
                        # Enhanced ContextItem with processing metadata
                        context_item = ContextItem(
                            source_task_id=child_node.task_id, 
                            source_task_goal=child_node.goal,
                            content=processed_content,
                            content_type_description=f"child_{child_status.value.lower()}_output_{processing_method}"
                        )
                        child_results_for_aggregator.append(context_item)
                        
                        logger.info(f"    Child {child_node.task_id}: {processing_method} ({len(processed_content)} chars)")
                
                logger.info(f"  Total child content for aggregation: {total_child_content_size} chars from {len(child_results_for_aggregator)} children")

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
            aggregator_adapter = context.agent_registry.get_agent_adapter(node, action_verb="aggregate")

            if not aggregator_adapter and agent_name_at_entry and node.agent_name != agent_name_at_entry:
                logger.debug(f"        AggregatingNodeHandler: Blueprint aggregator lookup failed. Trying original entry agent_name: {agent_name_at_entry}")
                node.agent_name = agent_name_at_entry
                aggregator_adapter = context.agent_registry.get_agent_adapter(node, action_verb="aggregate")

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
            active_adapter = context.agent_registry.get_agent_adapter(node, action_verb=action_verb_to_use)
            if active_adapter: is_modifier_agent = True

            if not active_adapter: 
                logger.warning(f"    NeedsReplan: No 'modify_plan' adapter resolved (tried: {node.agent_name}). Falling back to 'plan' adapter.")
                action_verb_to_use = "plan"
                is_modifier_agent = False
                # MODIFIED: Use get_planner_from_blueprint for consistent planner lookup
                lookup_name_for_replan_op = get_planner_from_blueprint(
                    context.current_agent_blueprint,
                    node.task_type,
                    agent_name_at_entry, # Fallback if blueprint provides nothing
                    node # Pass the node for root planner consideration
                )
                logger.debug(f"        NeedsReplan: Fallback to 'plan' adapter. Blueprint lookup via get_planner_from_blueprint returned: {lookup_name_for_replan_op}")
                
                node.agent_name = lookup_name_for_replan_op # Set for planner lookup
                active_adapter = context.agent_registry.get_agent_adapter(node, action_verb=action_verb_to_use) # Re-fetch adapter
                
                if not active_adapter and agent_name_at_entry and node.agent_name != agent_name_at_entry : 
                    node.agent_name = agent_name_at_entry
                    active_adapter = context.agent_registry.get_agent_adapter(node, action_verb=action_verb_to_use)

                if not active_adapter: # Still no planner? Fail.
                    node.update_status(TaskStatus.FAILED, error_msg="Fallback to Plan adapter failed during replan due to missing PlanModifier inputs & subsequent planner lookup failure.")
                    return
                logger.info(f"    NeedsReplanNodeHandler: Switched to Plan adapter '{getattr(active_adapter, 'agent_name', type(active_adapter).__name__)}' for replan.")
                # Input for the standard planner
                input_for_replan = resolve_input_for_planner_agent(
                    current_task_id=node.task_id, knowledge_store=context.knowledge_store,
                    overall_objective=current_overall_objective, planning_depth=node.layer,
                    replan_details=node.replan_details, global_constraints=getattr(context.task_graph, 'global_constraints', [])
                )
            else: 
                # Input for the standard planner (initial case or after 'modify_plan' adapter wasn't found first)
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
                
                # CRITICAL: Update the knowledge store immediately to ensure the status change is persisted
                context.knowledge_store.add_or_update_record_from_node(node)
                logger.info(f"✅ Node {node.task_id} status updated to NEEDS_REPLAN and persisted to knowledge store")
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