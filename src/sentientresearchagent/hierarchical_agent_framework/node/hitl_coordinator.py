from typing import Optional, Any, Dict, Union
from loguru import logger

from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskStatus
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import (
    PlannerInput, PlanOutput, AgentTaskInput, PlanModifierInput
)
from .node_configs import NodeProcessorConfig # For HITL feature flags
from sentientresearchagent.hierarchical_agent_framework.utils.hitl_utils import request_human_review
from sentientresearchagent.hierarchical_agent_framework.agents.utils import get_context_summary, TARGET_WORD_COUNT_FOR_CTX_SUMMARIES
from sentientresearchagent.hierarchical_agent_framework.graph.task_graph import TaskGraph
from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import KnowledgeStore
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskType # For type hinting

from agno.exceptions import StopAgentRun


class HITLCoordinator:
    """
    Coordinates Human-in-the-Loop (HITL) interactions based on configuration
    and provides a centralized point for HITL calls.
    """
    def __init__(self, config: NodeProcessorConfig):
        self.config = config
        logger.info(f"HITLCoordinator initialized with config: HITL Plan Gen={self.config.enable_hitl_after_plan_generation}, "
                    f"HITL Atomizer={self.config.enable_hitl_after_atomizer}, HITL Pre-Exec={self.config.enable_hitl_before_execute}")

    async def _call_hitl_interface(
        self,
        checkpoint_name: str,
        context_message: str,
        data_for_review: Optional[Any],
        node: TaskNode, # Node is needed to update its status in case of abort/error
        current_hitl_attempt: int = 1
    ) -> Dict[str, Any]:
        """
        Internal wrapper to call the actual HITL mechanism (request_human_review).
        Updates node status in case of abort/error directly within this call.
        Returns a dictionary indicating outcome.
        """
        try:
            hitl_response_from_util = await request_human_review(
                checkpoint_name=checkpoint_name,
                context_message=context_message,
                data_for_review=data_for_review,
                node_id=node.task_id,
                current_attempt=current_hitl_attempt
            )

            user_choice = hitl_response_from_util.get("user_choice")
            user_message = hitl_response_from_util.get("message", "N/A")
            modification_instructions = hitl_response_from_util.get("modification_instructions")

            if user_choice == "approved":
                logger.info(f"HITLCoordinator: Node {node.task_id} checkpoint '{checkpoint_name}' approved by user.")
                return {"status": "approved", "message": user_message}
            elif user_choice == "request_modification":
                logger.info(f"HITLCoordinator: Node {node.task_id} checkpoint '{checkpoint_name}' - user requested modification.")
                return {
                    "status": "request_modification",
                    "message": user_message,
                    "modification_instructions": modification_instructions
                }
            else: # Should not happen if hook logic is correct (aborted is via exception from request_human_review)
                logger.error(f"HITLCoordinator: Node {node.task_id} HITL for '{checkpoint_name}' returned unexpected choice: {user_choice}. Treating as error.")
                node.update_status(TaskStatus.FAILED, error_msg=f"Unexpected HITL user choice: {user_choice}")
                return {"status": "error", "message": f"Unexpected HITL user choice: {user_choice}"}

        except StopAgentRun as e:
            logger.warning(f"HITLCoordinator: Node {node.task_id} processing aborted by user at '{checkpoint_name}': {e.agent_message if hasattr(e, 'agent_message') else e}")
            node.update_status(TaskStatus.CANCELLED, result_summary=f"Cancelled by user at {checkpoint_name}: {e.agent_message if hasattr(e, 'agent_message') else str(e)}")
            return {"status": "aborted", "message": f"User aborted: {e.agent_message if hasattr(e, 'agent_message') else str(e)}"}

        except Exception as e:
            logger.exception(f"HITLCoordinator: Error during HITL interface for node {node.task_id}, checkpoint '{checkpoint_name}': {e}")
            node.update_status(TaskStatus.FAILED, error_msg=f"Critical error during HITL at {checkpoint_name}: {e}")
            return {"status": "error", "message": f"Critical HITL error: {str(e)}"}


    async def review_plan_generation(
        self, node: TaskNode, plan_output: PlanOutput, planner_input: Union[PlannerInput, PlanModifierInput], is_replan: bool = False
    ) -> Dict[str, Any]:
        # NEW: Check for root plan only mode
        if hasattr(self.config, 'hitl_root_plan_only') and self.config.hitl_root_plan_only:
            # In root plan only mode, only review root node (layer 0) initial plans
            if not (self.config.enable_hitl_after_plan_generation and node.layer == 0 and not is_replan):
                return {"status": "approved", "message": "HITL for plan generation skipped - root plan only mode (non-root or replan)."}
        else:
            # Original logic - review based on configuration and layer
            if not (self.config.enable_hitl_after_plan_generation and node.layer == 0):
                return {"status": "approved", "message": "HITL for plan generation skipped by configuration or node layer."}

        hitl_context_msg = f"Review {'re-generated plan' if is_replan else 'initial plan'} for task '{node.task_id}'. Goal: {node.goal}"
        plan_for_review = plan_output.model_dump(mode='json') if plan_output else {}
        
        context_items_for_summary = []
        overall_objective_for_hitl = ""
        current_task_goal_for_hitl = ""

        if isinstance(planner_input, PlannerInput):
            overall_objective_for_hitl = planner_input.overall_objective
            current_task_goal_for_hitl = planner_input.current_task_goal
            if hasattr(planner_input, 'execution_history_and_context') and planner_input.execution_history_and_context:
                 context_items_for_summary.extend(planner_input.execution_history_and_context.relevant_ancestor_outputs)
                 context_items_for_summary.extend(planner_input.execution_history_and_context.prior_sibling_task_outputs)
        elif isinstance(planner_input, PlanModifierInput):
            overall_objective_for_hitl = planner_input.overall_objective
            current_task_goal_for_hitl = node.goal 

        hitl_data = {
            "task_goal": node.goal,
            "proposed_plan": plan_for_review,
            "planner_input_summary": {
                "overall_objective": overall_objective_for_hitl,
                "current_task_summary": current_task_goal_for_hitl, 
                "context_summary": get_context_summary(context_items_for_summary, TARGET_WORD_COUNT_FOR_CTX_SUMMARIES)
            }
        }
        if is_replan and isinstance(planner_input, PlanModifierInput):
            hitl_data["user_modification_instructions"] = planner_input.user_modification_instructions
            if node.replan_details:
                 hitl_data["reason_for_current_replan"] = node.replan_details.reason_for_failure_or_replan

        return await self._call_hitl_interface(
            checkpoint_name=f"{'PostRePlanGeneration' if is_replan else 'PostInitialPlanGeneration'}",
            context_message=hitl_context_msg, 
            data_for_review=hitl_data, 
            node=node
        )

    async def review_atomizer_output(
        self, node: TaskNode, original_goal: str, updated_goal: str, 
        is_atomic: bool, proposed_next_action: str, context_summary: str
    ) -> Dict[str, Any]:
        if not self.config.enable_hitl_after_atomizer:
            return {"status": "approved", "message": "HITL for atomizer output skipped by configuration."}

        hitl_context_msg = (f"Review Atomizer output for task '{node.task_id}'. "
                            f"Original goal: '{original_goal[:100]}...'. "
                            f"Proposed: '{updated_goal[:100]}...'. Action: {proposed_next_action}.")
        hitl_data = {
            "original_goal": original_goal,
            "updated_goal": updated_goal,
            "atomizer_decision_is_atomic": is_atomic,
            "proposed_next_action": proposed_next_action, 
            "current_context_summary": context_summary
        }
        return await self._call_hitl_interface("PostAtomizerCheck", hitl_context_msg, hitl_data, node)

    async def review_before_execution(
        self, node: TaskNode, agent_task_input: AgentTaskInput
    ) -> Dict[str, Any]:
        if not self.config.enable_hitl_before_execute:
            return {"status": "approved", "message": "HITL before execution skipped by configuration."}

        hitl_context_msg = f"Review task before execution: '{node.goal}'. Agent: {node.agent_name or 'Default Executor'}"
        hitl_data = {
            "task_id": node.task_id,
            "goal": node.goal,
            "task_type": node.task_type.value if isinstance(node.task_type, TaskType) else str(node.task_type),
            "agent_name": node.agent_name,
            "input_context_summary": get_context_summary(agent_task_input.relevant_context_items, TARGET_WORD_COUNT_FOR_CTX_SUMMARIES)
        }
        return await self._call_hitl_interface("PreExecutionCheck", hitl_context_msg, hitl_data, node)

    async def review_modified_plan(
        self, node: TaskNode, modified_plan: PlanOutput, replan_attempt_count: int
    ) -> Dict[str, Any]:
        if not self.config.enable_hitl_after_modified_plan:
            return {"status": "approved", "message": "HITL for modified plan skipped by configuration."}

        checkpoint_name = f"PostModifiedPlanReview_Attempt_{replan_attempt_count}"
        hitl_context_msg = (
            f"Review modified plan for task '{node.task_id}' (Replan Attempt {replan_attempt_count}). "
            f"Goal: {node.goal}"
        )
        
        plan_for_review = modified_plan.model_dump(mode='json') if modified_plan else {}
        
        # You might want to include a summary of the original modification request or previous plan details
        # For now, we'll keep it concise with the newly proposed plan.
        original_modification_request = node.aux_data.get('user_modification_instructions', 'N/A')
        if isinstance(original_modification_request, PlanOutput): # Safety check if aux_data stores the model
            original_modification_request = "User provided new plan directly (details in original plan)."


        hitl_data = {
            "task_id": node.task_id,
            "task_goal": node.goal,
            "replan_attempt_count": replan_attempt_count,
            "reason_for_current_replan": node.replan_reason, # The reason that triggered this current replan
            "original_user_modification_request_for_this_cycle": original_modification_request,
            "proposed_modified_plan": plan_for_review,
        }
        
        # Adding a more specific instruction for the user during this review
        context_message_for_user = (
            f"{hitl_context_msg}\n\n"
            "The plan has been modified based on previous feedback (if any). Please review the new 'proposed_modified_plan'.\n"
            "You can 'approve' it, or 'request_modification' again with new instructions in the 'modification instructions' field. "
            "If you 'request_modification', the system will attempt to revise this proposed plan."
        )

        return await self._call_hitl_interface(
            checkpoint_name=checkpoint_name,
            context_message=context_message_for_user, # Use the more detailed message for the user
            data_for_review=hitl_data,
            node=node,
            current_hitl_attempt=replan_attempt_count # Pass the replan attempt as current_hitl_attempt
        )

    async def review_initial_project_goal(
        self, 
        root_node: TaskNode, 
        task_graph: TaskGraph, # Needed to update overall_project_goal
        knowledge_store: KnowledgeStore # Needed to log node updates
    ) -> None:
        """
        Performs HITL review for the root node's initial goal.
        Updates root_node.goal, task_graph.overall_project_goal, and knowledge_store.
        This method assumes the root_node is valid and corresponds to the project root.
        """
        if not root_node or root_node.task_id != "root": # Basic validation
            logger.error("HITLCoordinator: review_initial_project_goal called with invalid node.")
            return

        logger.info(f"HITLCoordinator: Triggering initial HITL review for root node {root_node.task_id} goal: '{root_node.goal}'.")
        
        # Data for review now includes the node's model_dump
        # context_message is more specific
        context_message = (
            f"Review the initial root task goal for the project: '{root_node.goal}'. "
            "You can approve it as is, or provide a modified goal in the 'modification instructions' field. "
            "If you abort, the project will be cancelled."
        )
        data_for_review = root_node.model_dump(mode='json') # Provide full node data for context

        # Call the internal HITL interface.
        # Note: _call_hitl_interface itself handles node status updates for FAILED/CANCELLED.
        hitl_outcome = await self._call_hitl_interface(
            checkpoint_name="RootNodeGoalReview",
            context_message=context_message,
            data_for_review=data_for_review,
            node=root_node
        )

        if hitl_outcome.get("status") == "approved":
            logger.info(f"HITLCoordinator: Root node {root_node.task_id} goal approved by user without changes.")
            # No changes to node.goal or task_graph.overall_project_goal needed.
            # Node status remains PENDING (or as set by _call_hitl_interface if error/abort).
            # Knowledge store already updated by _call_hitl_interface if status changed.

        elif hitl_outcome.get("status") == "request_modification":
            modified_goal = hitl_outcome.get("modification_instructions", "").strip()
            if modified_goal:
                logger.info(f"HITLCoordinator: Root node {root_node.task_id} goal modified by user from '{root_node.goal}' to '{modified_goal}'.")
                root_node.goal = modified_goal
                task_graph.overall_project_goal = modified_goal # Update task_graph as well
                knowledge_store.add_or_update_record_from_node(root_node) # Log the goal change
            else:
                logger.info(f"HITLCoordinator: Root node {root_node.task_id} goal approved (modification requested but no instructions given, using original).")
        
        # If "aborted" or "error", _call_hitl_interface has already updated node status and logged.
        # No further action needed here for those cases.
        # The calling function (e.g., in ExecutionEngine) will check root_node.status.
