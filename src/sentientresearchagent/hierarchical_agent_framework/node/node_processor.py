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
MAX_PLANNING_LAYER = 2 # Max depth for recursive planning
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

    async def _handle_ready_node(self, node: TaskNode, task_graph: TaskGraph, knowledge_store: KnowledgeStore):
        logger.info(f"  NodeProcessor: Handling READY node {node.task_id} (Original Type: {node.node_type}, Goal: '{node.goal[:30]}...')")
        
        try: 
            node.update_status(TaskStatus.RUNNING)
            # knowledge_store.add_or_update_record_from_node(node) # Moved to finally for guaranteed update

            action_to_take: NodeType
            current_task_type_value = node.task_type.value if isinstance(node.task_type, TaskType) else node.task_type
            
            atomizer_input_model = resolve_context_for_agent(
                current_task_id=node.task_id,
                current_goal=node.goal, 
                current_task_type=current_task_type_value,
                agent_name="default_atomizer", 
                knowledge_store=knowledge_store,
                overall_project_goal=task_graph.overall_project_goal
            )
            
            atomizer_adapter = get_agent_adapter(node, action_verb="atomize")

            if atomizer_adapter:
                logger.info(f"    NodeProcessor: Calling Atomizer for node {node.task_id}")
                # try/except for atomizer_adapter.process removed here, will be caught by main try/except if it fails
                atomizer_output: AtomizerOutput = await atomizer_adapter.process(node, atomizer_input_model)
                
                if atomizer_output.updated_goal != node.goal:
                    logger.info(f"    Atomizer updated goal for {node.task_id}: '{node.goal[:50]}...' -> '{atomizer_output.updated_goal[:50]}...'")
                    node.goal = atomizer_output.updated_goal
                
                action_to_take = NodeType.EXECUTE if atomizer_output.is_atomic else NodeType.PLAN
                node.node_type = action_to_take 
                
                logger.info(f"    Atomizer determined {node.task_id} as {action_to_take.name}. NodeType set to {node.node_type.name}.")
                # knowledge_store.add_or_update_record_from_node(node) # Moved to finally

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
                    if hitl_outcome_atomizer["status"] != "approved": # Aborted or error
                        # Node status already updated by _call_hitl
                        return 
            else: # No atomizer adapter
                logger.warning(f"    NodeProcessor: No AtomizerAdapter found for node {node.task_id}. Proceeding with original node_type: {node.node_type}")
                action_to_take = node.node_type if isinstance(node.node_type, NodeType) else NodeType(node.node_type)

            if action_to_take == NodeType.PLAN and node.layer >= self.config.max_planning_layer:
                logger.warning(f"    NodeProcessor: Max planning depth ({self.config.max_planning_layer}) reached for {node.task_id}. Forcing EXECUTE.")
                node.node_type = NodeType.EXECUTE 
                action_to_take = NodeType.EXECUTE
                # knowledge_store.add_or_update_record_from_node(node) # Moved to finally
            
            general_agent_task_input_model: Optional[AgentTaskInput] = None
            if action_to_take == NodeType.EXECUTE:
                general_agent_task_input_model = resolve_context_for_agent(
                    current_task_id=node.task_id,
                    current_goal=node.goal, 
                    current_task_type=current_task_type_value,
                    agent_name=f"agent_for_{current_task_type_value}", 
                    knowledge_store=knowledge_store,
                    overall_project_goal=task_graph.overall_project_goal
                )
                node.input_payload_dict = general_agent_task_input_model.model_dump()
                logger.debug(f"Node {node.task_id} input payload (for EXECUTE): {node.input_payload_dict}")

            if action_to_take == NodeType.PLAN:
                logger.info(f"    NodeProcessor: Preparing initial PlannerInput for {node.task_id} (Goal: '{node.goal[:50]}...')")
                current_overall_objective = node.overall_objective or getattr(task_graph, 'overall_project_goal', "Undefined overall project goal")
                
                initial_planner_adapter = get_agent_adapter(node, action_verb="plan") # Assuming 'node.node_type' is PLAN here
                if not initial_planner_adapter:
                    raise ValueError(f"No initial PLAN adapter found for node {node.task_id} (TaskType: {node.task_type}, NodeType: {node.node_type})")

                current_planner_input_model = resolve_input_for_planner_agent(
                    current_task_id=node.task_id, knowledge_store=knowledge_store,
                    overall_objective=current_overall_objective, planning_depth=node.layer,
                    replan_details=None, global_constraints=getattr(task_graph, 'global_constraints', [])
                )
                node.input_payload_dict = current_planner_input_model.model_dump() # Log initial input
                current_plan_output: Optional[PlanOutput] = await initial_planner_adapter.process(node, current_planner_input_model)

                # Check if HITL for plan generation is enabled AND if the current node is the root node (layer 0)
                if self.config.enable_hitl_after_plan_generation and node.layer == 0:
                    max_modification_attempts = 3
                    modification_attempts = 0
                    plan_approved = False
                    # Key for retrieving the PlanModifierAdapter from AGENT_REGISTRY
                    PLAN_MODIFIER_ADAPTER_KEY = "PlanModifier" # Must match registration in agents/__init__.py

                    while modification_attempts < max_modification_attempts:
                        modification_attempts += 1
                        
                        current_plan_display_data = []
                        if current_plan_output and current_plan_output.sub_tasks:
                            current_plan_display_data = current_plan_output.model_dump().get("sub_tasks", [])
                        
                        hitl_context_msg_key = "Review generated plan"
                        if not (current_plan_output and current_plan_output.sub_tasks):
                             hitl_context_msg_key = "Planner returned no sub-tasks. Review options"
                        
                        hitl_context_msg = f"{hitl_context_msg_key} for task '{node.task_id}' (Review attempt {modification_attempts})."
                        hitl_data = {
                            "parent_task_goal": node.goal,
                            "planned_sub_tasks": current_plan_display_data
                        }
                        
                        hitl_outcome = await self._call_hitl(
                            "PlanReview", hitl_context_msg, hitl_data, node,
                            current_hitl_attempt=modification_attempts
                        )

                        if hitl_outcome["status"] == "aborted": return
                        elif hitl_outcome["status"] == "approved":
                            plan_approved = True
                            logger.info(f"Node {node.task_id}: Plan approved by user after {modification_attempts} review attempt(s).")
                            break 
                        elif hitl_outcome["status"] == "request_modification":
                            user_instructions = hitl_outcome.get('modification_instructions', '').strip()
                            logger.info(f"Node {node.task_id}: User requested plan modification (Attempt {modification_attempts}). Instructions: '{user_instructions}'")
                            
                            if not user_instructions: # Should be caught by hook, but double check
                                logger.warning(f"Node {node.task_id}: Empty modification instructions received. Re-presenting current plan.")
                                if modification_attempts >= max_modification_attempts: break # Avoid infinite loop if hook somehow allows empty
                                continue

                            if modification_attempts >= max_modification_attempts:
                                logger.warning(f"Node {node.task_id}: Max plan modification attempts ({max_modification_attempts}) reached. Proceeding with the current plan or failing.")
                                break 

                            # --- PHASE 2: Actual Re-planning using PlanModifierAgent ---
                            if not current_plan_output: # Should not happen if instructions were given for a plan
                                logger.error(f"Node {node.task_id}: Cannot modify plan as current_plan_output is None. This state should be handled better.")
                                # Potentially break or try to re-run initial planner if this makes sense
                                break # For safety, exit HITL loop

                            try:
                                plan_modifier_adapter = NAMED_AGENTS.get(PLAN_MODIFIER_ADAPTER_KEY) # Get directly by key
                                if not plan_modifier_adapter:
                                    logger.error(f"Node {node.task_id}: PlanModifierAdapter ('{PLAN_MODIFIER_ADAPTER_KEY}') not found in NAMED_AGENTS. Cannot re-plan.")
                                    # Fallback: re-present current plan or break
                                    break # Break HITL loop if modifier not available

                                plan_modifier_input = PlanModifierInput(
                                    original_plan=current_plan_output,
                                    user_modification_instructions=user_instructions,
                                    overall_objective=current_overall_objective, # Pass parent's objective
                                    parent_task_id=node.task_id,
                                    planning_depth=node.layer
                                )
                                
                                logger.info(f"Node {node.task_id}: Calling PlanModifierAdapter with user instructions.")
                                # Update input_payload_dict for logging/transparency if desired
                                node.input_payload_dict = {"plan_modifier_input": plan_modifier_input.model_dump(exclude_none=True)}
                                
                                revised_plan_output: Optional[PlanOutput] = await plan_modifier_adapter.process(node, plan_modifier_input)
                                
                                if revised_plan_output:
                                    logger.success(f"Node {node.task_id}: PlanModifierAdapter returned a revised plan.")
                                    current_plan_output = revised_plan_output # Update current plan with the revision
                                else:
                                    logger.warning(f"Node {node.task_id}: PlanModifierAdapter returned no plan. Retaining previous plan for next review.")
                                    # current_plan_output remains the same, user will see it again.
                            
                            except Exception as replan_ex:
                                logger.exception(f"Node {node.task_id}: Error during plan modification call: {replan_ex}. Retaining previous plan.")
                                # current_plan_output remains the same.

                            # Loop continues to present the (potentially) new current_plan_output
                        
                        elif hitl_outcome["status"] == "error": return
                        else: 
                            logger.error(f"Node {node.task_id}: Unexpected HITL outcome status: {hitl_outcome.get('status')}. Aborting.")
                            node.update_status(TaskStatus.FAILED, error_msg="Internal error in HITL plan review loop.")
                            return
                    # --- End of HITL while loop ---

                    if not plan_approved and modification_attempts >= max_modification_attempts:
                        logger.warning(f"Node {node.task_id}: Plan not explicitly approved after max HITL attempts. Proceeding with current plan if available.")
                
                # --- After HITL Loop or if HITL is disabled / not applicable ---
                if current_plan_output and current_plan_output.sub_tasks: # Check if a valid plan exists
                    self._create_sub_nodes_from_plan(node, current_plan_output, task_graph, knowledge_store)
                    node.update_status(TaskStatus.PLAN_DONE, result=current_plan_output.model_dump())
                else: 
                    logger.warning(f"    NodeProcessor: No valid plan for {node.task_id} after planning/HITL. Converting to EXECUTE.")
                    node.node_type = NodeType.EXECUTE
                    if general_agent_task_input_model is None: 
                        general_agent_task_input_model = resolve_context_for_agent( # ... (args as before) ... )
                            current_task_id=node.task_id, current_goal=node.goal,
                            current_task_type=current_task_type_value, agent_name=f"agent_for_{current_task_type_value}",
                            knowledge_store=knowledge_store, overall_project_goal=task_graph.overall_project_goal
                        )
                        node.input_payload_dict = general_agent_task_input_model.model_dump()

                    if self.config.enable_hitl_before_execute:
                        hitl_outcome_exec = await self._call_hitl("PreExecuteCheckFromPlan", # ... (args as before) ... )
                           f"Review execution for task '{node.task_id}' (converted from PLAN due to no plan).",
                           { "task_goal": node.goal, "task_type": current_task_type_value,
                             "input_context_summary": get_context_summary(general_agent_task_input_model.context_items if general_agent_task_input_model else [])},
                           node
                        )
                        if hitl_outcome_exec["status"] != "approved": return
                    await self._execute_node_action(node, general_agent_task_input_model, task_graph, knowledge_store)
            
            elif action_to_take == NodeType.EXECUTE:
                 if general_agent_task_input_model is None: 
                     logger.error(f"NodeProcessor CRITICAL: general_agent_task_input_model is None for EXECUTE node {node.task_id}")
                     raise ValueError(f"Input model not prepared for EXECUTE node {node.task_id}")

                 if self.config.enable_hitl_before_execute:
                    hitl_outcome_direct_exec = await self._call_hitl("PreExecuteCheckDirect", # ... (args as before) ... )
                        f"Review execution for task '{node.task_id}'.",
                        { "task_goal": node.goal, "task_type": current_task_type_value,
                          "input_context_summary": get_context_summary(general_agent_task_input_model.context_items if general_agent_task_input_model else []) },
                        node
                    )
                    if hitl_outcome_direct_exec["status"] != "approved": return
                 await self._execute_node_action(node, general_agent_task_input_model, task_graph, knowledge_store)
            else: 
                error_msg = f"Unexpected node action type: {action_to_take} for node {node.task_id}"
                logger.error(f"  NodeProcessor Error: {error_msg}")
                # node.update_status(TaskStatus.FAILED, error_msg=error_msg) # Status update in finally
                raise ValueError(error_msg)

        except StopAgentRun as e: 
            if node.status not in [TaskStatus.CANCELLED, TaskStatus.FAILED]: 
                logger.warning(f"  NodeProcessor: StopAgentRun caught for node {node.task_id}. Marking as CANCELLED. Message: {e.agent_message if hasattr(e, 'agent_message') else e}")
                node.update_status(TaskStatus.CANCELLED, result_summary=f"Operation cancelled via StopAgentRun: {e.agent_message if hasattr(e, 'agent_message') else str(e)}")
        except Exception as e:
            logger.exception(f"  NodeProcessor Error: Failed to process READY node {node.task_id}")
            if node.status not in [TaskStatus.CANCELLED, TaskStatus.FAILED]: 
                 node.update_status(TaskStatus.FAILED, error_msg=str(e))
        finally:
            knowledge_store.add_or_update_record_from_node(node)
            logger.debug(f"  NodeProcessor: Final status for node {node.task_id} after handling: {node.status.value if node.status else 'Unknown'}")

    async def _execute_node_action(self, node: TaskNode, agent_task_input: AgentTaskInput, task_graph: TaskGraph, knowledge_store: KnowledgeStore):
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
        execution_result = await executor_adapter.process(node, agent_task_input)
        
        node.output_type_description = f"{type(execution_result).__name__}_result"
        
        if execution_result is not None:
            # TODO: Implement robust summarization.
            # For Pydantic models, check if they have a summary method/attribute.
            if hasattr(execution_result, 'get_summary_for_context') and callable(execution_result.get_summary_for_context):
                node.output_summary = execution_result.get_summary_for_context()
                logger.debug(f"NodeProcessor: Used 'get_summary_for_context()' for {node.task_id}'s output_summary.")
            elif hasattr(execution_result, 'summary') and isinstance(getattr(execution_result, 'summary'), str):
                 node.output_summary = str(execution_result.summary)
                 logger.debug(f"NodeProcessor: Used '.summary' attribute for {node.task_id}'s output_summary.")
            elif isinstance(execution_result, str):
                # If the result itself is a string, summarize it if it's too long
                if len(execution_result.split()) > TARGET_WORD_COUNT_FOR_CTX_SUMMARIES * 0.8: # Heuristic: if it's already a decent length string
                    logger.debug(f"NodeProcessor: Result for {node.task_id} is a string, attempting summarization.")
                    node.output_summary = get_context_summary(execution_result, target_word_count=TARGET_WORD_COUNT_FOR_CTX_SUMMARIES)
                else: # If it's a short string, use as is
                    node.output_summary = execution_result
                logger.debug(f"NodeProcessor: String result for {node.task_id} processed for output_summary (len: {len(node.output_summary)}). First 50: '{node.output_summary[:50]}'")
            elif isinstance(execution_result, CustomSearcherOutput):
                logger.debug(f"NodeProcessor: Result for {node.task_id} is CustomSearcherOutput. Summarizing 'output_text_with_citations' and appending annotations.")
                text_to_summarize = execution_result.output_text_with_citations
                summary_text = get_context_summary(text_to_summarize, target_word_count=TARGET_WORD_COUNT_FOR_CTX_SUMMARIES)
                
                citations_str = ""
                if execution_result.annotations:
                    citation_parts = ["\n\nCitations:"]
                    for idx, ann in enumerate(execution_result.annotations):
                        title = ann.title or "Source"
                        citation_parts.append(f"- [{title}]({ann.url})")
                    citations_str = "\n".join(citation_parts)
                
                node.output_summary = summary_text + citations_str
                # Store the full CustomSearcherOutput in result, so original annotations list is preserved
                node.result = execution_result 
                node.output_type_description = "CustomSearcherOutput_with_summary_and_citations"
            elif isinstance(execution_result, BaseModel): # For other Pydantic models
                logger.debug(f"NodeProcessor: Result for {node.task_id} is a generic BaseModel {type(execution_result).__name__}. Summarizing its JSON representation.")
                # Fallback to summarizing the JSON representation if no better text part found
                node.output_summary = get_context_summary(execution_result, target_word_count=TARGET_WORD_COUNT_FOR_CTX_SUMMARIES) 
            else:
                logger.debug(f"NodeProcessor: Result for {node.task_id} is of unknown type {type(execution_result).__name__} for summarization. Using str().")
                node.output_summary = str(execution_result)[:500] + "..." if len(str(execution_result)) > 500 else str(execution_result)
            
            if node.output_summary:
                logger.success(f"    NodeProcessor: Set output_summary for {node.task_id} (len {len(node.output_summary)}): '{node.output_summary[:100]}...'")
            else:
                logger.warning(f"    NodeProcessor: output_summary for {node.task_id} ended up empty.")

        if isinstance(execution_result, str) and execution_result.startswith("<<NEEDS_REPLAN>>"):
            replan_reason = execution_result.replace("<<NEEDS_REPLAN>>", "").strip()
            logger.warning(f"    NodeProcessor: Node {node.task_id} requested REPLAN. Reason: {replan_reason}")
            # Ensure status update uses the Enum member
            node.update_status(TaskStatus.NEEDS_REPLAN, result=replan_reason)
        else:
            # Ensure status update uses the Enum member
            node.update_status(TaskStatus.DONE, result=execution_result)

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

    async def _handle_needs_replan_node(self, node: TaskNode, task_graph: TaskGraph, knowledge_store: KnowledgeStore):
        logger.info(f"  NodeProcessor: Handling NEEDS_REPLAN node {node.task_id} (Goal: '{node.goal[:50]}...')")
        
        # Simple mechanism to prevent infinite re-planning loops for a single node.
        # This would ideally be a field on the TaskNode itself.
        if not hasattr(node, '_replan_attempts'):
            node._replan_attempts = 0
        
        if node._replan_attempts >= MAX_REPLAN_ATTEMPTS:
            logger.error(f"  NodeProcessor: Max re-plan attempts ({MAX_REPLAN_ATTEMPTS}) reached for node {node.task_id}. Marking as FAILED.")
            node.update_status(TaskStatus.FAILED, error_msg=f"Max re-plan attempts ({MAX_REPLAN_ATTEMPTS}) reached.")
            knowledge_store.add_or_update_record_from_node(node)
            return

        node._replan_attempts += 1
        node.update_status(TaskStatus.RUNNING, result=f"Re-planning attempt {node._replan_attempts}") # Mark as RUNNING during re-plan
        knowledge_store.add_or_update_record_from_node(node)

        failed_sub_goals_info = []
        successful_sibling_outputs = [] # For context to the new plan

        if node.sub_graph_id:
            previous_sub_nodes = task_graph.get_nodes_in_graph(node.sub_graph_id)
            for sub_node in previous_sub_nodes:
                if sub_node.status == TaskStatus.FAILED:
                    failed_sub_goals_info.append(
                        f"Sub-task '{sub_node.goal[:100]}' (ID: {sub_node.task_id}) failed with error: {sub_node.error or 'Unknown error'}"
                    )
                elif sub_node.status == TaskStatus.DONE:
                    # These could be passed as context to the new planning attempt
                    # This reuses the ExecutionHistoryItem structure from PlannerInput's context part
                    successful_sibling_outputs.append(
                        ExecutionHistoryItem(
                            task_goal=sub_node.goal,
                            outcome_summary=sub_node.output_summary or str(sub_node.result)[:200], # Provide a summary
                            full_output_reference_id=sub_node.task_id 
                        )
                    )
        
        if not failed_sub_goals_info:
            logger.warning(f"  NodeProcessor: Node {node.task_id} is NEEDS_REPLAN, but no failed sub-tasks found in subgraph {node.sub_graph_id}. Defaulting to general replan.")
            reason_for_replan = "General re-plan requested, but no specific sub-task failures were identified in the previous attempt. Review the overall goal and previous plan structure."
            failed_sub_goal_summary = node.goal # Re-plan the main goal
        else:
            reason_for_replan = "One or more sub-tasks failed in the previous execution. New plan must address these failures. Failures:\n- " + "\n- ".join(failed_sub_goals_info)
            # For simplicity, we'll just use the parent node's goal as the "failed_sub_goal" for the replan request,
            # as the planner is re-planning for this parent node. The detailed reasons contain the specifics.
            failed_sub_goal_summary = node.goal 


        replan_details = ReplanRequestDetails(
            failed_sub_goal=failed_sub_goal_summary, # The goal of the current PLAN node that needs re-planning
            reason_for_failure_or_replan=reason_for_replan,
            previous_attempt_output_summary=f"Previous plan for '{node.goal[:50]}' resulted in failures. Successful sibling outputs from that attempt are provided in context if any.",
            specific_guidance_for_replan="Review the failed sub-task goals and their errors. Propose a new set of sub-tasks that either breaks down the failed parts more effectively, tries a different approach, or correctly utilizes results from previously successful sibling tasks."
        )

        try:
            current_overall_objective = node.overall_objective or getattr(task_graph, 'overall_project_goal', "Undefined overall project goal")
            
            # The planner_input now includes `successful_sibling_outputs` in its context part
            # This assumes `resolve_input_for_planner_agent` can accept and integrate this.
            # We might need to adjust `resolve_input_for_planner_agent` or construct the input more manually here.
            # For now, let's prepare it and pass it. `resolve_input_for_planner_agent` might need prior_sibling_task_outputs
            
            # We need to ensure `resolve_input_for_planner_agent` correctly uses these.
            # The `execution_history_and_context` field in PlannerInput is the place.
            # `prior_sibling_task_outputs` usually refers to siblings of the *current node being planned*.
            # In a re-plan, these successful_sibling_outputs are from the *previous attempt* of this node's sub-graph.
            # This fits the spirit if not the exact prior definition.

            planner_input_model = resolve_input_for_planner_agent(
                current_task_id=node.task_id,
                knowledge_store=knowledge_store,
                overall_objective=current_overall_objective,
                planning_depth=node.layer, # Keep same layer, it's a re-plan
                replan_details=replan_details,
                # Pass successful parts of the previous plan as context
                # This field might need adjustment in `resolve_input_for_planner_agent`
                # or we inject it directly into the context model.
                # For now, let's assume `resolve_input_for_planner_agent` handles `replan_details` primarily
                # and we rely on KS for other context. We can refine context for replanning later.
                # Let's manually create the execution_history_and_context for now for clarity
                # to include outputs from the *failed plan's successful siblings*.
                execution_history_override=ExecutionHistoryAndContext(
                    prior_sibling_task_outputs=successful_sibling_outputs, # These are children from the last failed plan
                    relevant_ancestor_outputs=[], # Ancestor context should be resolved normally by `resolve_input_for_planner_agent`
                    global_knowledge_base_summary=None # Let resolver handle this
                )
            )
            # Override what `resolve_input_for_planner_agent` might put in prior_sibling_task_outputs
            # if we pass execution_history_override.
            # The `resolve_input_for_planner_agent` may need a new parameter to accept this cleanly.
            # For now, this demonstrates the intent. The `PlannerInput` schema has `execution_history_and_context`.

            logger.info(f"    NodeProcessor: Preparing PlannerInput for REPLAN of {node.task_id} (Goal: '{node.goal[:50]}...')")
            node.input_payload_dict = planner_input_model.model_dump() # Log the input

            planner_adapter = get_agent_adapter(node, action_verb="plan")
            if not planner_adapter:
                raise ValueError(f"No PLAN adapter found for re-planning node {node.task_id}")

            new_plan_output: PlanOutput = await planner_adapter.process(node, planner_input_model)

            if not new_plan_output or not new_plan_output.sub_tasks:
                logger.warning(f"    NodeProcessor: Re-Planner for {node.task_id} returned no sub-tasks. Marking node as FAILED.")
                node.update_status(TaskStatus.FAILED, error_msg="Re-planning attempt by planner resulted in an empty plan.")
            else:
                logger.success(f"    NodeProcessor: Re-Planner for {node.task_id} returned a new plan with {len(new_plan_output.sub_tasks)} sub-tasks.")
                # Archive or mark old sub-graph nodes? For now, they remain as FAILED/DONE.
                # A new sub_graph_id will be used for the new plan.
                
                # Important: Create a new sub_graph_id for the new plan
                new_sub_graph_id = f"subgraph_{node.task_id}_replan_{node._replan_attempts}"
                node.sub_graph_id = new_sub_graph_id # Update node to point to the new sub-graph
                # task_graph.add_graph(new_sub_graph_id) # _create_sub_nodes_from_plan will do this if it doesn't exist

                node.planned_sub_task_ids.clear() # Clear out old sub-task IDs

                self._create_sub_nodes_from_plan(node, new_plan_output, task_graph, knowledge_store)
                node.update_status(TaskStatus.PLAN_DONE, result=f"Re-plan attempt {node._replan_attempts} successful. New plan created.")
        
        except Exception as e:
            logger.exception(f"  NodeProcessor Error: Failed to re-plan node {node.task_id}")
            node.update_status(TaskStatus.FAILED, error_msg=f"Re-planning failed: {str(e)}")
        
        knowledge_store.add_or_update_record_from_node(node) # Final update for status, result, etc.

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
