from typing import List, Optional, Any, Dict
from pydantic import BaseModel
from loguru import logger
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskStatus, NodeType, TaskType
from sentientresearchagent.hierarchical_agent_framework.graph.task_graph import TaskGraph
from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import KnowledgeStore
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import (
    AgentTaskInput, PlanOutput, AtomizerOutput, ContextItem,
    PlannerInput, ReplanRequestDetails,
    CustomSearcherOutput, PlanModifierInput # Added for type checking in output_summary
)
from sentientresearchagent.hierarchical_agent_framework.agents.registry import get_agent_adapter, NAMED_AGENTS
from sentientresearchagent.hierarchical_agent_framework.agents.base_adapter import BaseAdapter # For type hinting
from sentientresearchagent.hierarchical_agent_framework.context.context_builder import (
    resolve_context_for_agent,
    resolve_input_for_planner_agent
)
# NEW IMPORT for summarization utility
from sentientresearchagent.hierarchical_agent_framework.agents.utils import get_context_summary, TARGET_WORD_COUNT_FOR_CTX_SUMMARIES
# NEW IMPORT for deepcopy if needed for context items, though typically Pydantic handles this well.
# import copy

# Configuration
MAX_PLANNING_LAYER = 1 # Max depth for recursive planning
MAX_REPLAN_ATTEMPTS = 1 # Max number of times a single PLAN node can attempt to re-plan.

# Import the new HITL utility
from sentientresearchagent.hierarchical_agent_framework.utils.hitl_utils import request_human_review

# Configuration for NodeProcessor, including HITL flags
class NodeProcessorConfig(BaseModel):
    enable_hitl_after_plan_generation: bool = True 
    enable_hitl_after_atomizer: bool = False
    enable_hitl_before_execute: bool = False
    max_planning_layer: int = 2
    max_replan_attempts: int = 1

class NodeProcessor:
    """Handles the processing of a single TaskNode's action."""

    def __init__(self, config: Optional[NodeProcessorConfig] = None):
        logger.info("NodeProcessor initialized.")
        self.config = config if config else NodeProcessorConfig()
        # No need to instantiate a separate HITL service here if request_human_review is a static/module function

    async def _call_hitl(
        self, 
        checkpoint_name: str, 
        context_message: str, 
        data_for_review: Optional[Any], 
        node: TaskNode,
        current_hitl_attempt: int = 1 # For passing to request_human_review
    ) -> Dict[str, Any]: # Return type changed to Dict
        """
        Wrapper to call the HITL mechanism.
        Returns a dictionary indicating outcome:
        {
            "status": "approved" | "aborted" | "request_modification" | "error",
            "message": "User message or error details",
            "modification_instructions": "text if status is 'request_modification'"
        }
        StopAgentRun exception from request_human_review (on abort) will be caught here.
        """
        try:
            hitl_response_from_util = await request_human_review(
                checkpoint_name=checkpoint_name,
                context_message=context_message,
                data_for_review=data_for_review,
                node_id=node.task_id,
                current_attempt=current_hitl_attempt # Pass attempt number
            )
            
            user_choice = hitl_response_from_util.get("user_choice")
            user_message = hitl_response_from_util.get("message", "N/A")
            modification_instructions = hitl_response_from_util.get("modification_instructions")

            if user_choice == "approved":
                logger.info(f"Node {node.task_id}: HITL checkpoint '{checkpoint_name}' approved by user.")
                return {"status": "approved", "message": user_message}
            elif user_choice == "request_modification":
                logger.info(f"Node {node.task_id}: HITL checkpoint '{checkpoint_name}' - user requested modification.")
                return {
                    "status": "request_modification", 
                    "message": user_message,
                    "modification_instructions": modification_instructions
                }
            else: # Should not happen if hook logic is correct (aborted is via exception)
                logger.error(f"Node {node.task_id}: HITL for '{checkpoint_name}' returned unexpected choice: {user_choice}. Treating as error.")
                node.update_status(TaskStatus.FAILED, error_msg=f"Unexpected HITL user choice: {user_choice}")
                return {"status": "error", "message": f"Unexpected HITL user choice: {user_choice}"}

        except StopAgentRun as e: 
            logger.warning(f"Node {node.task_id} processing aborted by user (StopAgentRun caught by _call_hitl) at '{checkpoint_name}': {e.agent_message if hasattr(e, 'agent_message') else e}")
            node.update_status(TaskStatus.CANCELLED, result_summary=f"Cancelled by user at {checkpoint_name}: {e.agent_message if hasattr(e, 'agent_message') else str(e)}")
            # knowledge_store.add_or_update_record_from_node(node) # Done in _handle_ready_node's finally
            return {"status": "aborted", "message": f"User aborted: {e.agent_message if hasattr(e, 'agent_message') else str(e)}"}

        except Exception as e:
            logger.exception(f"Node {node.task_id}: Error during _call_hitl for checkpoint '{checkpoint_name}': {e}")
            node.update_status(TaskStatus.FAILED, error_msg=f"Critical error during HITL at {checkpoint_name}: {e}")
            # knowledge_store.add_or_update_record_from_node(node) # Done in _handle_ready_node's finally
            return {"status": "error", "message": f"Critical HITL error: {str(e)}"}

    def _create_sub_nodes_from_plan(self, parent_node: TaskNode, plan_output: PlanOutput, task_graph: TaskGraph, knowledge_store: KnowledgeStore):
        """
        Creates TaskNode instances from a plan list, adds them to the graph,
        sets up dependencies based on `depends_on_indices`, and updates the parent_node.
        """
        if not parent_node.sub_graph_id:
            parent_node.sub_graph_id = f"subgraph_{parent_node.task_id}"
            task_graph.add_graph(parent_node.sub_graph_id)
            logger.info(f"    NodeProcessor: Created new subgraph '{parent_node.sub_graph_id}' for parent '{parent_node.task_id}'")
        
        sub_graph_id = parent_node.sub_graph_id
        parent_node.planned_sub_task_ids.clear()

        created_sub_nodes: list[TaskNode] = []

        for i, sub_task_def in enumerate(plan_output.sub_tasks):
            sub_node_id = f"{parent_node.task_id}.{i+1}" # Simple sequential ID based on order in plan

            try:
                task_type_enum = TaskType[sub_task_def.task_type.upper()]
                node_type_enum = NodeType[sub_task_def.node_type.upper()]
            except KeyError as e:
                error_msg = f"Invalid task_type or node_type string ('{sub_task_def.task_type}'/'{sub_task_def.node_type}') in plan for parent {parent_node.task_id}: {e}"
                logger.error(f"    NodeProcessor Error: {error_msg}")
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
            knowledge_store.add_or_update_record_from_node(sub_node)
            parent_node.planned_sub_task_ids.append(sub_node.task_id)
            logger.success(f"      Added sub-node: {sub_node} to graph {sub_graph_id}")

        # Add dependencies based on the 'depends_on_indices' field
        for i, sub_node in enumerate(created_sub_nodes):
            sub_task_def = plan_output.sub_tasks[i] # Get the corresponding sub_task_def
            if hasattr(sub_task_def, 'depends_on_indices') and sub_task_def.depends_on_indices:
                for dep_index in sub_task_def.depends_on_indices:
                    if 0 <= dep_index < len(created_sub_nodes) and dep_index != i:
                        dependency_node = created_sub_nodes[dep_index]
                        task_graph.add_edge(sub_graph_id, dependency_node.task_id, sub_node.task_id)
                        logger.info(f"      Added dependency edge: {dependency_node.task_id} -> {sub_node.task_id} in graph {sub_graph_id}")
                    else:
                        logger.warning(f"    NodeProcessor: Invalid dependency index {dep_index} for sub-task {sub_node.task_id} (index {i}). Skipping this dependency.")
            # If depends_on_indices is empty or not present, the node has no explicit dependencies on its siblings in this plan.
            # It will become READY once its parent (the PLAN node) is PLAN_DONE.

        logger.info(f"    NodeProcessor: Created {len(created_sub_nodes)} sub-nodes for parent {parent_node.task_id} with specified dependencies.")

    async def _atomize_node_if_needed(
        self, node: TaskNode, task_graph: TaskGraph, knowledge_store: KnowledgeStore
    ) -> Optional[NodeType]:
        """
        Calls the Atomizer agent to determine if the node's goal is atomic.
        Updates node.goal and node.node_type based on atomizer output.
        Handles HITL after atomization if enabled.
        Returns the NodeType to proceed with (PLAN or EXECUTE), or None if HITL caused an abort/error.
        """
        current_task_type_value = node.task_type.value if isinstance(node.task_type, TaskType) else node.task_type
        
        atomizer_input_model = resolve_context_for_agent(
            current_task_id=node.task_id,
            current_goal=node.goal,
            current_task_type=current_task_type_value,
            agent_name="default_atomizer",
            knowledge_store=knowledge_store,
            overall_project_goal=task_graph.overall_project_goal
        )
        
        atomizer_adapter = get_agent_adapter(node, action_verb="atomize") # Node type is not yet set by atomizer here
        action_to_take: NodeType

        if atomizer_adapter:
            logger.info(f"    NodeProcessor: Calling Atomizer for node {node.task_id}")
            atomizer_output: AtomizerOutput = await atomizer_adapter.process(node, atomizer_input_model)
            
            if atomizer_output.updated_goal != node.goal:
                logger.info(f"    Atomizer updated goal for {node.task_id}: '{node.goal[:50]}...' -> '{atomizer_output.updated_goal[:50]}...'")
                node.goal = atomizer_output.updated_goal
            
            action_to_take = NodeType.EXECUTE if atomizer_output.is_atomic else NodeType.PLAN
            node.node_type = action_to_take 
            
            logger.info(f"    Atomizer determined {node.task_id} as {action_to_take.name}. NodeType set to {node.node_type.name}.")

            if self.config.enable_hitl_after_atomizer:
                hitl_context_msg = f"Review Atomizer output for task '{node.task_id}'."
                hitl_data = {
                    "original_goal": atomizer_input_model.current_goal,
                    "updated_goal": node.goal,
                    "atomizer_decision_is_atomic": atomizer_output.is_atomic,
                    "proposed_next_action": action_to_take.value, 
                    "current_context_summary": get_context_summary(atomizer_input_model.context_items)
                }
                hitl_outcome_atomizer = await self._call_hitl("PostAtomizerCheck", hitl_context_msg, hitl_data, node)
                if hitl_outcome_atomizer["status"] != "approved": 
                    return None 
            return action_to_take
        else: 
            logger.warning(f"    NodeProcessor: No AtomizerAdapter found for node {node.task_id}. Proceeding with original node_type: {node.node_type}")
            # Ensure node.node_type is an Enum instance
            if isinstance(node.node_type, str):
                 try:
                    resolved_node_type = NodeType(node.node_type)
                    node.node_type = resolved_node_type # Assign the enum to the node instance
                    return resolved_node_type
                 except ValueError:
                    logger.error(f"Invalid NodeType string '{node.node_type}' for node {node.task_id} when atomizer is absent. Defaulting to EXECUTE.")
                    node.node_type = NodeType.EXECUTE # Update node instance
                    return NodeType.EXECUTE
            elif isinstance(node.node_type, NodeType):
                return node.node_type # Already an enum, node.node_type is correct
            else: 
                logger.error(f"Unexpected type for node.node_type: {type(node.node_type)}. Defaulting to EXECUTE.")
                node.node_type = NodeType.EXECUTE # Update node instance
                return NodeType.EXECUTE


    async def _handle_ready_plan_node(
        self, node: TaskNode, task_graph: TaskGraph, knowledge_store: KnowledgeStore
    ):
        """Handles a READY node that needs to be PLANNED."""
        logger.info(f"    NodeProcessor: Planning for node {node.task_id} (Goal: '{node.goal[:50]}...')")
        current_overall_objective = node.overall_objective or getattr(task_graph, 'overall_project_goal', "Undefined overall project goal")
        
        planner_adapter = get_agent_adapter(node, action_verb="plan")
        if not planner_adapter:
            error_msg = f"No PLAN adapter found for node {node.task_id} (TaskType: {node.task_type}) after atomization or explicit PLAN type."
            logger.error(error_msg)
            node.update_status(TaskStatus.FAILED, error_msg=error_msg)
            return

        current_planner_input_model = resolve_input_for_planner_agent(
            current_task_id=node.task_id, knowledge_store=knowledge_store,
            overall_objective=current_overall_objective, planning_depth=node.layer,
            replan_details=None, 
            global_constraints=getattr(task_graph, 'global_constraints', [])
        )
        node.input_payload_dict = current_planner_input_model.model_dump()
        
        plan_output: Optional[PlanOutput] = await planner_adapter.process(node, current_planner_input_model)

        if plan_output is None or not plan_output.sub_tasks:
            if node.status not in [TaskStatus.CANCELLED, TaskStatus.FAILED]: 
                logger.warning(f"    Node {node.task_id} (PLAN): Planner returned no sub-tasks or None. Considering this a planning failure or no-op.")
                if plan_output is None:
                    node.update_status(TaskStatus.FAILED, error_msg="Planner failed to produce an output.")
                else: 
                    logger.info(f"    Node {node.task_id} (PLAN): Planner returned an empty list of sub-tasks. Interpreting as task being atomic.")
                    node.node_type = NodeType.EXECUTE 
                    node.output_summary = "Planner determined no further sub-tasks are needed; task is atomic."
                    node.update_status(TaskStatus.PLAN_DONE) 
            return 

        if self.config.enable_hitl_after_plan_generation and node.layer == 0:
            hitl_context_msg_plan = f"Review initial plan for root task '{node.task_id}'."
            plan_for_review = plan_output.model_dump(mode='json') if plan_output else {}
            
            # Combine context items for summary
            context_items_for_summary = (
                current_planner_input_model.execution_history_and_context.relevant_ancestor_outputs + 
                current_planner_input_model.execution_history_and_context.prior_sibling_task_outputs
            )

            hitl_data_plan = {
                "task_goal": node.goal,
                "proposed_plan": plan_for_review,
                "planner_input_summary": {
                    "overall_objective": current_planner_input_model.overall_objective,
                    "current_task_summary": current_planner_input_model.current_task_goal, 
                    "context_summary": get_context_summary(context_items_for_summary)
                }
            }
            hitl_outcome_plan = await self._call_hitl("PostInitialPlanGeneration", hitl_context_msg_plan, hitl_data_plan, node)

            if hitl_outcome_plan["status"] == "request_modification":
                logger.info(f"Node {node.task_id}: Plan modification requested by user. Setting to NEEDS_REPLAN.")
                node.replan_reason = f"User requested modification: {hitl_outcome_plan.get('modification_instructions', 'No specific instructions.')}"
                node.update_status(TaskStatus.NEEDS_REPLAN)
                node.result = plan_output 
                node.output_summary = "Initial plan requires user modification."
                return 
            elif hitl_outcome_plan["status"] != "approved": 
                return

        self._create_sub_nodes_from_plan(node, plan_output, task_graph, knowledge_store)
        node.result = plan_output 
        node.output_summary = f"Planned {len(plan_output.sub_tasks)} sub-tasks."
        node.update_status(TaskStatus.PLAN_DONE)
        logger.success(f"    NodeProcessor: Node {node.task_id} planning complete. Status: {node.status.name}")


    async def _handle_ready_execute_node(
        self, node: TaskNode, task_graph: TaskGraph, knowledge_store: KnowledgeStore
    ):
        """Handles a READY node that needs to be EXECUTED."""
        logger.info(f"    NodeProcessor: Executing node {node.task_id} (TaskType: {node.task_type}, Goal: '{node.goal[:50]}...')")
        
        current_task_type_value = node.task_type.value if isinstance(node.task_type, TaskType) else node.task_type

        # Prepare input for the execution agent
        # If node.input_payload_dict is already populated (e.g., by atomizer or forced execute),
        # we might want to use it, or re-resolve context. For now, let's re-resolve to ensure freshness,
        # unless a specific flag indicates otherwise.
        # The original logic prepared general_agent_task_input_model before the PLAN/EXECUTE split.
        
        agent_task_input_model = resolve_context_for_agent(
            current_task_id=node.task_id,
            current_goal=node.goal,
            current_task_type=current_task_type_value, # Pass the string value
            agent_name=node.agent_name or f"agent_for_{current_task_type_value}", # Use node.agent_name if specified
            knowledge_store=knowledge_store,
            overall_project_goal=task_graph.overall_project_goal
        )
        node.input_payload_dict = agent_task_input_model.model_dump()
        logger.debug(f"Node {node.task_id} input payload (for EXECUTE): {node.input_payload_dict}")

        if self.config.enable_hitl_before_execute:
            hitl_context_msg_exec = f"Review before executing task '{node.task_id}'."
            hitl_data_exec = {
                "task_goal": node.goal,
                "task_type": current_task_type_value,
                "resolved_input_summary": {
                    "current_task_summary": agent_task_input_model.current_task_description,
                     "context_summary": get_context_summary(agent_task_input_model.context_items, max_items=5)
                }
            }
            hitl_outcome_exec = await self._call_hitl("PreExecutionCheck", hitl_context_msg_exec, hitl_data_exec, node)
            if hitl_outcome_exec["status"] != "approved":
                # Node status already updated by _call_hitl
                return

        # Get the appropriate adapter for EXECUTE action
        # The node.node_type should be EXECUTE at this point.
        executor_adapter = get_agent_adapter(node, action_verb="execute")
        if not executor_adapter:
            error_msg = f"No EXECUTE adapter found for node {node.task_id} (TaskType: {node.task_type}, NodeType: {node.node_type})"
            logger.error(error_msg)
            node.update_status(TaskStatus.FAILED, error_msg=error_msg)
            return

        adapter_display_name = getattr(executor_adapter, 'agent_name', type(executor_adapter).__name__)
        logger.info(f"    NodeProcessor: Calling executor adapter '{adapter_display_name}' for node {node.task_id}")
        execution_result: Optional[Any] = await executor_adapter.process(node, agent_task_input_model)

        if execution_result is not None:
            node.result = execution_result
            # Determine output_summary (similar to _execute_node_action)
            if isinstance(execution_result, BaseModel):
                try:
                    # Try to get a summary if the model supports it, else use a generic one
                    if hasattr(execution_result, 'summary') and execution_result.summary:
                        node.output_summary = str(execution_result.summary)
                    elif hasattr(execution_result, 'content_summary') and execution_result.content_summary: # For WebSearchResultsOutput
                        node.output_summary = str(execution_result.content_summary)
                    elif isinstance(execution_result, CustomSearcherOutput):
                        summary_text = str(execution_result)[:100] + "..." if len(str(execution_result)) > 100 else str(execution_result)
                        annotation_count = len(execution_result.annotations) if execution_result.annotations else 0
                        node.output_summary = f"Search result: \"{summary_text}\" ({annotation_count} annotations)"
                    elif isinstance(execution_result, PlanModifierInput): # This seems unlikely as output for EXECUTE
                        node.output_summary = f"Plan modification result." # Placeholder
                    else:
                        node.output_summary = f"Execution completed. Result type: {type(execution_result).__name__}"
                except Exception as e:
                    logger.warning(f"Error generating summary from BaseModel result for {node.task_id}: {e}")
                    node.output_summary = f"Execution completed. Result type: {type(execution_result).__name__} (summary error)."
            elif isinstance(execution_result, str):
                node.output_summary = execution_result[:250] + "..." if len(execution_result) > 250 else execution_result
            else:
                node.output_summary = f"Execution completed. Data stored in result."
            
            node.update_status(TaskStatus.DONE)
            logger.success(f"    NodeProcessor: Node {node.task_id} execution complete. Status: {node.status.name}. Summary: {node.output_summary}")
        else:
            # If adapter.process returns None, it might indicate an issue handled within the adapter (e.g. HITL abort)
            # or an actual failure to produce a result.
            # The node status should ideally be set by the adapter or _call_hitl in such cases.
            if node.status not in [TaskStatus.CANCELLED, TaskStatus.FAILED]:
                logger.warning(f"    NodeProcessor: Executor for {node.task_id} returned None. Marking as FAILED if not already handled.")
                node.update_status(TaskStatus.FAILED, error_msg="Executor returned no result.")


    async def _handle_ready_node(self, node: TaskNode, task_graph: TaskGraph, knowledge_store: KnowledgeStore):
        logger.info(f"  NodeProcessor: Handling READY node {node.task_id} (Original NodeType: {node.node_type.value if isinstance(node.node_type, NodeType) else node.node_type}, Goal: '{node.goal[:30]}...')")
        
        try: 
            node.update_status(TaskStatus.RUNNING)

            # 1. Atomize node if applicable
            # The _atomize_node_if_needed method updates node.node_type and node.goal.
            # It returns the NodeType to proceed with, or None if HITL aborted.
            action_to_take_after_atomizer = await self._atomize_node_if_needed(node, task_graph, knowledge_store)

            if action_to_take_after_atomizer is None: # HITL intervention stopped processing
                logger.info(f"Node {node.task_id} processing halted after atomizer/HITL.")
                return # Node status already updated by _call_hitl or _atomize_node_if_needed

            # Override node.node_type if it wasn't set by atomizer (e.g. no atomizer found)
            # This ensures node.node_type is the one decided by atomization or original if no atomizer.
            if node.node_type is None: # Should be set by atomizer or fallback in _atomize_node_if_needed
                 node.node_type = action_to_take_after_atomizer


            # 2. Check max planning depth if the action is PLAN
            if node.node_type == NodeType.PLAN and node.layer >= self.config.max_planning_layer:
                logger.warning(f"    NodeProcessor: Max planning depth ({self.config.max_planning_layer}) reached for {node.task_id}. Forcing EXECUTE.")
                node.node_type = NodeType.EXECUTE # Update node's type
                # knowledge_store.add_or_update_record_from_node(node) # Done in finally
            
            # 3. Dispatch to specific handler based on the (potentially updated) node.node_type
            current_action_type = node.node_type # This is the definitive type after atomization and depth check

            if current_action_type == NodeType.PLAN:
                await self._handle_ready_plan_node(node, task_graph, knowledge_store)
            elif current_action_type == NodeType.EXECUTE:
                # Execute node might need an AgentTaskInput model.
                # The original logic prepared this before the PLAN/EXECUTE split.
                # _handle_ready_execute_node will resolve its own context.
                await self._handle_ready_execute_node(node, task_graph, knowledge_store)
            
            # AGGREGATE and other types are typically not handled from a READY state directly.
            # They transition to these states after their prerequisites are met.
            # The main process_node will route them if they are in READY state but are AGGREGATE type initially.
            elif current_action_type == NodeType.AGGREGATE:
                 # This case implies an AGGREGATE node was somehow set to READY and not handled by atomizer to be PLAN/EXECUTE
                 # This should typically go to _handle_aggregating_node if status was AGGREGATING
                 logger.warning(f"Node {node.task_id} is of type AGGREGATE but in READY status. Attempting to process via _handle_aggregating_node.")
                 # This might need status check or adjustment if _handle_aggregating_node expects AGGREGATING status
                 # For now, let's assume it's an anomaly and log it.
                 # If it's truly ready to aggregate, it should have a different status.
                 # We might need to transition its status or this indicates a logic flaw elsewhere.
                 # For safety, let's mark as error for now if an AGGREGATE node is in READY state here.
                 node.update_status(TaskStatus.FAILED, error_msg=f"Node {node.task_id} is AGGREGATE type but was handled in READY state pathway inappropriately.")

            else:
                # This case should ideally not be reached if NodeType is well-defined
                # and atomizer correctly sets PLAN/EXECUTE.
                logger.error(f"Node {node.task_id}: Unhandled NodeType '{node.node_type}' in _handle_ready_node after atomization. Setting to FAILED.")
                node.update_status(TaskStatus.FAILED, error_msg=f"Unhandled NodeType '{node.node_type}' for READY node.")

        except Exception as e:
            logger.exception(f"Node {node.task_id}: Unhandled exception in _handle_ready_node: {e}")
            # Ensure status reflects error if not already FAILED or CANCELLED
            if node.status not in [TaskStatus.FAILED, TaskStatus.CANCELLED]:
                 node.update_status(TaskStatus.FAILED, error_msg=f"Unhandled error: {str(e)}")
        finally:
            logger.info(f"  NodeProcessor: Finished handling for node {node.task_id}. Final status: {node.status.name if node.status else 'Unknown'}")
            knowledge_store.add_or_update_record_from_node(node)


    # Removed _execute_node_action as its logic is now primarily within _handle_ready_execute_node
    # If there are parts of _execute_node_action that were generic and reusable, they should be utility functions
    # or part of the adapter itself.

    async def _handle_aggregating_node(self, node: TaskNode, task_graph: TaskGraph, knowledge_store: KnowledgeStore):
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
            aggregated_result = await aggregator_adapter.process(node, agent_task_input)
            
            node.output_type_description = "aggregated_text_result"
            # Ensure status update uses the Enum member
            node.update_status(TaskStatus.DONE, result=aggregated_result)

        except Exception as e:
            logger.error(f"  NodeProcessor Error: Failed to process AGGREGATING node {node.task_id}: {e}")
            # Ensure status update uses the Enum member
            node.update_status(TaskStatus.FAILED, error_msg=str(e))
        
        knowledge_store.add_or_update_record_from_node(node) # Final update

    async def process_node(self, node: TaskNode, task_graph: TaskGraph, knowledge_store: KnowledgeStore):
        """
        Processes a node based on its status.
        This method is called by the ExecutionEngine.
        """
        status_display = node.status.name if isinstance(node.status, TaskStatus) else node.status
        logger.info(f"NodeProcessor: Received node {node.task_id} (Goal: '{node.goal[:30]}...') with status {status_display}")

        current_status = node.status if isinstance(node.status, TaskStatus) else TaskStatus(node.status)
        
        if current_status == TaskStatus.READY:
            await self._handle_ready_node(node, task_graph, knowledge_store)
        elif current_status == TaskStatus.AGGREGATING:
            await self._handle_aggregating_node(node, task_graph, knowledge_store)
        elif current_status == TaskStatus.NEEDS_REPLAN:
            await self._handle_needs_replan_node(node, task_graph, knowledge_store)
        else:
            logger.warning(f"  NodeProcessor Warning: process_node called on node {node.task_id} with status {status_display} - no action taken.")
