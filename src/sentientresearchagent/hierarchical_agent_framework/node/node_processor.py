from typing import List, Optional, Any, Dict
from pydantic import BaseModel
from loguru import logger

from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskStatus, NodeType, TaskType
from sentientresearchagent.hierarchical_agent_framework.graph.task_graph import TaskGraph
from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import KnowledgeStore
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import (
    AgentTaskInput, PlanOutput, AtomizerOutput, ContextItem,
    PlannerInput, ReplanRequestDetails,
    CustomSearcherOutput, PlanModifierInput
)
from sentientresearchagent.hierarchical_agent_framework.agents.registry import get_agent_adapter, NAMED_AGENTS
from sentientresearchagent.hierarchical_agent_framework.agents.base_adapter import BaseAdapter
from sentientresearchagent.hierarchical_agent_framework.context.context_builder import (
    resolve_context_for_agent,
    resolve_input_for_planner_agent
)
from sentientresearchagent.hierarchical_agent_framework.agents.utils import get_context_summary, TARGET_WORD_COUNT_FOR_CTX_SUMMARIES
from .node_creation_utils import SubNodeCreator
from .node_atomizer_utils import NodeAtomizer
from .node_configs import NodeProcessorConfig
# Remove direct import of request_human_review and StopAgentRun if no longer used directly
# from sentientresearchagent.hierarchical_agent_framework.utils.hitl_utils import request_human_review
# from agno.exceptions import StopAgentRun
# Import HITLCoordinator
from .hitl_coordinator import HITLCoordinator


MAX_PLANNING_LAYER = 1
MAX_REPLAN_ATTEMPTS = 1


class NodeProcessor:
    """Handles the processing of a single TaskNode's action."""

    def __init__(self,
                 task_graph: TaskGraph,
                 knowledge_store: KnowledgeStore,
                 config: Optional[NodeProcessorConfig] = None):
        logger.info("NodeProcessor initialized.")
        self.config = config if config else NodeProcessorConfig()
        self.task_graph = task_graph
        self.knowledge_store = knowledge_store
        
        # Instantiate HITLCoordinator first as NodeAtomizer needs it
        self.hitl_coordinator = HITLCoordinator(self.config)
        
        self.sub_node_creator = SubNodeCreator(task_graph, knowledge_store)
        # Pass HITLCoordinator instance to NodeAtomizer
        self.node_atomizer = NodeAtomizer(self.hitl_coordinator)


    # _call_hitl method is now removed from NodeProcessor. Its logic is in HITLCoordinator._call_hitl_interface

    async def _handle_ready_plan_node(
        self, node: TaskNode
    ):
        logger.info(f"    NodeProcessor: Planning for node {node.task_id} (Goal: '{node.goal[:50]}...')")
        current_overall_objective = node.overall_objective or getattr(self.task_graph, 'overall_project_goal', "Undefined overall project goal")

        planner_adapter = get_agent_adapter(node, action_verb="plan")
        if not planner_adapter:
            error_msg = f"No PLAN adapter found for node {node.task_id} (TaskType: {node.task_type}) after atomization or explicit PLAN type."
            logger.error(error_msg)
            node.update_status(TaskStatus.FAILED, error_msg=error_msg)
            return

        current_planner_input_model = resolve_input_for_planner_agent(
            current_task_id=node.task_id,
            knowledge_store=self.knowledge_store,
            overall_objective=current_overall_objective,
            planning_depth=node.layer,
            replan_details=None, # type: ignore
            global_constraints=getattr(self.task_graph, 'global_constraints', [])
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
                    node.update_status(TaskStatus.PLAN_DONE)
            return

        # Use HITLCoordinator for plan review
        hitl_outcome_plan = await self.hitl_coordinator.review_plan_generation(
            node=node,
            plan_output=plan_output,
            planner_input=current_planner_input_model
        )

        if hitl_outcome_plan["status"] == "request_modification":
            logger.info(f"Node {node.task_id}: Plan modification requested by user. Setting to NEEDS_REPLAN.")
            node.replan_details = ReplanRequestDetails(
                original_plan=plan_output,
                modification_instructions=hitl_outcome_plan.get('modification_instructions', 'No specific instructions.')
            ).model_dump()
            node.replan_reason = f"User requested modification: {hitl_outcome_plan.get('modification_instructions', 'No specific instructions.')}"
            node.update_status(TaskStatus.NEEDS_REPLAN)
            node.result = plan_output 
            node.output_summary = "Initial plan requires user modification."
            return
        elif hitl_outcome_plan["status"] != "approved": # Aborted or error
            # Node status already updated by HITLCoordinator
            return

        self.sub_node_creator.create_sub_nodes(node, plan_output)
        node.result = plan_output
        node.output_summary = f"Planned {len(plan_output.sub_tasks)} sub-tasks."
        node.update_status(TaskStatus.PLAN_DONE)
        logger.success(f"    NodeProcessor: Node {node.task_id} planning complete. Status: {node.status.name}")


    async def _handle_ready_execute_node(
        self, node: TaskNode
    ):
        logger.info(f"    NodeProcessor: Executing node {node.task_id} (Goal: '{node.goal[:50]}...')")

        agent_task_input_model = resolve_context_for_agent(
            current_task_id=node.task_id,
            current_goal=node.goal,
            current_task_type=node.task_type.value if isinstance(node.task_type, TaskType) else str(node.task_type),
            knowledge_store=self.knowledge_store,
            agent_name=node.agent_name,
            overall_project_goal=self.task_graph.overall_project_goal
        )
        node.input_payload_dict = agent_task_input_model.model_dump()

        # Use HITLCoordinator for pre-execution review
        hitl_outcome_exec = await self.hitl_coordinator.review_before_execution(
            node=node,
            agent_task_input=agent_task_input_model
        )
        if hitl_outcome_exec["status"] != "approved":
            # Node status should be updated by HITLCoordinator
            return

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
            # ... (summary generation logic remains the same)
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
                    elif isinstance(execution_result, PlanModifierInput):
                        node.output_summary = "Plan modification result."
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
            if node.status not in [TaskStatus.CANCELLED, TaskStatus.FAILED]:
                logger.warning(f"    NodeProcessor: Executor for {node.task_id} returned None. Marking as FAILED if not already handled.")
                node.update_status(TaskStatus.FAILED, error_msg="Executor returned no result.")


    async def _handle_ready_node(self, node: TaskNode, task_graph: TaskGraph, knowledge_store: KnowledgeStore):
        logger.info(f"  NodeProcessor: Handling READY node {node.task_id} (Original NodeType: {node.node_type.value if isinstance(node.node_type, NodeType) else node.node_type}, Goal: '{node.goal[:30]}...')")
        
        try: 
            node.update_status(TaskStatus.RUNNING)
            action_to_take_after_atomizer = await self.node_atomizer.atomize_node(node, task_graph, knowledge_store)

            if action_to_take_after_atomizer is None: 
                logger.info(f"Node {node.task_id} processing halted after atomizer/HITL attempt.")
                return 

            if node.node_type == NodeType.PLAN and node.layer >= self.config.max_planning_layer: # type: ignore
                logger.warning(f"    NodeProcessor: Max planning depth ({self.config.max_planning_layer}) reached for {node.task_id}. Forcing EXECUTE.")
                node.node_type = NodeType.EXECUTE # type: ignore
            
            current_action_type = node.node_type

            if current_action_type == NodeType.PLAN:
                await self._handle_ready_plan_node(node)
            elif current_action_type == NodeType.EXECUTE:
                await self._handle_ready_execute_node(node)
            
            elif current_action_type == NodeType.AGGREGATE:
                 node.update_status(TaskStatus.FAILED, error_msg=f"Node {node.task_id} is AGGREGATE type but was handled in READY state pathway inappropriately.")

            else:
                logger.error(f"Node {node.task_id}: Unhandled NodeType '{node.node_type}' in _handle_ready_node after atomization. Setting to FAILED.")
                node.update_status(TaskStatus.FAILED, error_msg=f"Unhandled NodeType '{node.node_type}' for READY node.")

        except Exception as e:
            logger.exception(f"Node {node.task_id}: Unhandled exception in _handle_ready_node: {e}")
            if node.status not in [TaskStatus.FAILED, TaskStatus.CANCELLED]:
                 node.update_status(TaskStatus.FAILED, error_msg=f"Unhandled error: {str(e)}")
        finally:
            logger.info(f"  NodeProcessor: Finished handling for node {node.task_id}. Final status: {node.status.name if node.status else 'Unknown'}")
            self.knowledge_store.add_or_update_record_from_node(node)


    async def _handle_aggregating_node(self, node: TaskNode, task_graph: TaskGraph, knowledge_store: KnowledgeStore):
        # ... (logic remains the same, no direct HITL calls here currently) ...
        logger.info(f"  NodeProcessor: Handling AGGREGATING node {node.task_id} (Goal: '{node.goal[:30]}...')")
        node.update_status(TaskStatus.RUNNING) 
        self.knowledge_store.add_or_update_record_from_node(node)


        child_results_for_aggregator: List[ContextItem] = []
        if node.sub_graph_id:
            child_nodes = self.task_graph.get_nodes_in_graph(node.sub_graph_id)
            for child_node in child_nodes:
                child_status = child_node.status if isinstance(child_node.status, TaskStatus) else TaskStatus(child_node.status) # type: ignore
                if child_status in [TaskStatus.DONE, TaskStatus.FAILED]: 
                     child_results_for_aggregator.append(ContextItem(
                        source_task_id=child_node.task_id,
                        source_task_goal=child_node.goal,
                        content=child_node.result if child_status == TaskStatus.DONE else child_node.error,
                        content_type_description=f"child_{child_status.value.lower()}_output" 
                    ))
        
        agent_task_input = AgentTaskInput(
            current_task_id=node.task_id,
            current_goal=node.goal,
            current_task_type=TaskType.AGGREGATE.value, 
            relevant_context_items=child_results_for_aggregator,
            overall_project_goal=self.task_graph.overall_project_goal 
        )
        node.input_payload_dict = agent_task_input.model_dump() 
        logger.debug(f"Node {node.task_id} input payload (aggregator): {node.input_payload_dict}")

        try:
            if not isinstance(node.node_type, NodeType):
                node.node_type = NodeType(node.node_type) # type: ignore

            aggregator_adapter = get_agent_adapter(node, action_verb="aggregate")
            if not aggregator_adapter:
                raise ValueError(f"No AGGREGATE adapter found for node {node.task_id}")

            logger.info(f"    NodeProcessor: Invoking AGGREGATE adapter '{type(aggregator_adapter).__name__}' for {node.task_id}")
            aggregated_result = await aggregator_adapter.process(node, agent_task_input)
            
            node.output_type_description = "aggregated_text_result" # type: ignore
            node.update_status(TaskStatus.DONE, result=aggregated_result)

        except Exception as e:
            logger.error(f"  NodeProcessor Error: Failed to process AGGREGATING node {node.task_id}: {e}")
            node.update_status(TaskStatus.FAILED, error_msg=str(e))


    async def _handle_needs_replan_node(self, node: TaskNode, task_graph: TaskGraph, knowledge_store: KnowledgeStore):
        # ... (logic remains the same, no direct HITL calls here currently that need changing to HITLCoordinator) ...
        # If future HITL is added here, it should use self.hitl_coordinator
        logger.info(f"  NodeProcessor: Handling NEEDS_REPLAN node {node.task_id} (Replan Attempts: {node.replan_attempts}, Goal: '{node.goal[:30]}...')")

        if node.replan_attempts >= self.config.max_replan_attempts:
            logger.warning(f"    Node {node.task_id}: Max replan attempts ({self.config.max_replan_attempts}) reached. Marking as FAILED.")
            node.update_status(TaskStatus.FAILED, error_msg="Max replan attempts reached.")
            return

        node.replan_attempts += 1
        node.update_status(TaskStatus.RUNNING) 

        try:
            node.node_type = NodeType.PLAN 
            
            plan_modifier_adapter = get_agent_adapter(node, action_verb="modify_plan") 
            if not plan_modifier_adapter:
                logger.warning(f"No 'modify_plan' adapter found for {node.task_id}. Falling back to default 'plan' adapter.")
                plan_modifier_adapter = get_agent_adapter(node, action_verb="plan")

            if not plan_modifier_adapter:
                error_msg = f"No suitable adapter (modify_plan or plan) found for NEEDS_REPLAN node {node.task_id}."
                logger.error(error_msg)
                node.update_status(TaskStatus.FAILED, error_msg=error_msg)
                return
            
            original_plan_data = None
            modification_instructions = node.replan_reason 
            
            if node.replan_details:
                try:
                    details = ReplanRequestDetails.model_validate(node.replan_details) # type: ignore
                    original_plan_data = details.original_plan
                    modification_instructions = details.modification_instructions
                except Exception as val_err:
                    logger.warning(f"Could not parse ReplanRequestDetails for {node.task_id}: {val_err}. Using raw replan_details if it's a dict.")
                    if isinstance(node.replan_details, dict): 
                        original_plan_data = node.replan_details.get('original_plan') # type: ignore
                        modification_instructions = node.replan_details.get('modification_instructions', node.replan_reason) # type: ignore


            if not original_plan_data and isinstance(node.result, PlanOutput): 
                 original_plan_data = node.result
            elif not original_plan_data and isinstance(node.result, dict): 
                try:
                    original_plan_data = PlanOutput.model_validate(node.result)
                except Exception: 
                    logger.warning(f"Could not parse node.result into PlanOutput for {node.task_id} during replan.")
            
            replan_input_details = None
            if original_plan_data or modification_instructions : 
                 replan_input_details = ReplanRequestDetails(
                    original_plan=original_plan_data, # type: ignore
                    modification_instructions=modification_instructions
                 )

            current_overall_objective = node.overall_objective or getattr(self.task_graph, 'overall_project_goal', "Undefined overall project goal")
            planner_input_model = resolve_input_for_planner_agent(
                current_task_id=node.task_id,
                knowledge_store=self.knowledge_store,
                overall_objective=current_overall_objective, # type: ignore
                planning_depth=node.layer,
                replan_details=replan_input_details, 
                global_constraints=getattr(self.task_graph, 'global_constraints', [])
            )
            node.input_payload_dict = planner_input_model.model_dump()


            logger.info(f"    NodeProcessor: Calling adapter '{getattr(plan_modifier_adapter, 'agent_name', type(plan_modifier_adapter).__name__)}' for replanning node {node.task_id}.")
            new_plan_output: Optional[PlanOutput] = await plan_modifier_adapter.process(node, planner_input_model)

            if new_plan_output and new_plan_output.sub_tasks:
                logger.info(f"    Node {node.task_id}: Replanning successful. New plan has {len(new_plan_output.sub_tasks)} sub-tasks.")
                if node.sub_graph_id:
                    logger.info(f"    Node {node.task_id}: Previous sub_graph_id was {node.sub_graph_id}. New plan will replace its tasks.")
                
                self.sub_node_creator.create_sub_nodes(node, new_plan_output)
                node.result = new_plan_output
                node.output_summary = f"Replanned with {len(new_plan_output.sub_tasks)} sub-tasks after {node.replan_attempts} attempt(s)."
                node.update_status(TaskStatus.PLAN_DONE)
                node.replan_reason = None 
                node.replan_details = None 
            else:
                logger.warning(f"    Node {node.task_id}: Replanning adapter returned no new sub-tasks. Marking as FAILED.")
                node.update_status(TaskStatus.FAILED, error_msg="Replanning failed to produce new sub-tasks.")

        except Exception as e:
            logger.exception(f"  NodeProcessor Error: Failed to process NEEDS_REPLAN node {node.task_id}: {e}")
            node.update_status(TaskStatus.FAILED, error_msg=f"Error during replanning: {str(e)}")


    async def process_node(self, node: TaskNode, task_graph: TaskGraph, knowledge_store: KnowledgeStore):
        status_display = node.status.name if isinstance(node.status, TaskStatus) else node.status
        logger.info(f"NodeProcessor: Received node {node.task_id} (Goal: '{node.goal[:30]}...') with status {status_display}")

        current_status = node.status if isinstance(node.status, TaskStatus) else TaskStatus(node.status) # type: ignore
        
        original_node_type_for_logging = node.node_type 
        
        try:
            if current_status == TaskStatus.READY:
                await self._handle_ready_node(node, task_graph, knowledge_store)
            elif current_status == TaskStatus.AGGREGATING:
                await self._handle_aggregating_node(node, task_graph, knowledge_store)
            elif current_status == TaskStatus.NEEDS_REPLAN:
                await self._handle_needs_replan_node(node, task_graph, knowledge_store)
            else:
                logger.warning(f"  NodeProcessor Warning: process_node called on node {node.task_id} with status {status_display} - no action taken.")
        except Exception as e: 
            logger.exception(f"NodeProcessor: Uncaught exception in process_node for {node.task_id} (Status: {status_display}, Type: {original_node_type_for_logging}): {e}") # type: ignore
            if node.status not in [TaskStatus.FAILED, TaskStatus.CANCELLED]:
                node.update_status(TaskStatus.FAILED, error_msg=f"Critical error in NodeProcessor.process_node: {str(e)}")
        finally:
            if self.knowledge_store: 
                 self.knowledge_store.add_or_update_record_from_node(node)
            else:
                logger.error("NodeProcessor: KnowledgeStore not available in process_node.final_update. State may not be saved.")
            logger.info(f"NodeProcessor: Finished processing node {node.task_id}. Final status: {node.status.name if node.status else 'Unknown'}")


# Define ProcessorContext for passing dependencies to handlers
class ProcessorContext:
    def __init__(self,
                 task_graph: TaskGraph,
                 knowledge_store: KnowledgeStore,
                 config: NodeProcessorConfig,
                 hitl_coordinator: HITLCoordinator,
                 sub_node_creator: SubNodeCreator,
                 node_atomizer: NodeAtomizer):
        self.task_graph = task_graph
        self.knowledge_store = knowledge_store
        self.config = config
        self.hitl_coordinator = hitl_coordinator
        self.sub_node_creator = sub_node_creator
        self.node_atomizer = node_atomizer