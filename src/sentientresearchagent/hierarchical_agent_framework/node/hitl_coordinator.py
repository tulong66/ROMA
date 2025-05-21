from typing import Optional, Any, Dict
from loguru import logger

from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskStatus
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import (
    PlannerInput, PlanOutput, AgentTaskInput
)
from .node_configs import NodeProcessorConfig # For HITL feature flags
from sentientresearchagent.hierarchical_agent_framework.utils.hitl_utils import request_human_review
from sentientresearchagent.hierarchical_agent_framework.agents.utils import get_context_summary, TARGET_WORD_COUNT_FOR_CTX_SUMMARIES

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
        self, node: TaskNode, plan_output: PlanOutput, planner_input: PlannerInput
    ) -> Dict[str, Any]:
        if not (self.config.enable_hitl_after_plan_generation and node.layer == 0): # Typically only for root/initial plans
            return {"status": "approved", "message": "HITL for plan generation skipped by configuration or node layer."}

        hitl_context_msg = f"Review initial plan for root task '{node.task_id}'. Current Goal: {node.goal}"
        plan_for_review = plan_output.model_dump(mode='json') if plan_output else {}
        
        context_items_for_summary = []
        if hasattr(planner_input, 'execution_history_and_context') and planner_input.execution_history_and_context:
             context_items_for_summary.extend(planner_input.execution_history_and_context.relevant_ancestor_outputs)
             context_items_for_summary.extend(planner_input.execution_history_and_context.prior_sibling_task_outputs)

        hitl_data = {
            "task_goal": node.goal,
            "proposed_plan": plan_for_review,
            "planner_input_summary": {
                "overall_objective": planner_input.overall_objective,
                "current_task_summary": planner_input.current_task_goal, 
                "context_summary": get_context_summary(context_items_for_summary, TARGET_WORD_COUNT_FOR_CTX_SUMMARIES)
            }
        }
        return await self._call_hitl_interface("PostInitialPlanGeneration", hitl_context_msg, hitl_data, node)

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
