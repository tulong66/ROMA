from abc import ABC, abstractmethod
from typing import Dict, Any, Union, List
from loguru import logger # Add this
from agno.agent import Agent as AgnoAgent # Renaming to avoid conflict if we define our own Agent interface
# It's good practice to also import the async version if available and distinct
# from agno.agent import AsyncAgent as AsyncAgnoAgent # Assuming such an import exists for type hinting
import asyncio # Add this import

from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode # For type hinting
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import (
    ContextItem, PlanOutput, AtomizerOutput, AgentTaskInput, PlannerInput, ExecutionHistoryItem
)

# Import prompt templates
from .prompts import INPUT_PROMPT, AGGREGATOR_PROMPT

class BaseAdapter(ABC):
    """
    Abstract base class for all agent adapters in this framework.
    An adapter is responsible for interfacing between the framework's
    TaskNode/context and a specific agent implementation (e.g., an AgnoAgent).
    """
    @abstractmethod
    async def process(self, node: TaskNode, agent_task_input: Any) -> Any: # Changed to async def
        """
        Processes a TaskNode using the adapted agent.

        Args:
            node: The TaskNode to process.
            agent_task_input: The structured input for the agent (usually AgentTaskInput).
                              Contains current_goal, context_items, etc.

        Returns:
            The result from the agent, which could be a Pydantic model (like PlanOutput),
            a string, or a structure for multi-modal content.
        """
        pass

class LlmApiAdapter(BaseAdapter):
    """
    Base adapter for agents implemented using the Agno library.
    This adapter simplifies interaction by leveraging Agno's native
    structured output and tool handling.
    """
    def __init__(self, agno_agent_instance: AgnoAgent, agent_name: str = "UnnamedAgnoAgent"): # Consider if agno_agent_instance should be AsyncAgnoAgent
        """
        Args:
            agno_agent_instance: The instantiated AgnoAgent.
            agent_name: A descriptive name for logging.
        """
        if not isinstance(agno_agent_instance, AgnoAgent): # Check against AsyncAgnoAgent if that's the expected type
            raise ValueError("llm_agent_instance must be an instance of agno.agent.Agent or its async equivalent")
        self.agno_agent = agno_agent_instance
        self.agent_name = agent_name if agent_name else (getattr(agno_agent_instance, 'name', None) or "UnnamedAgnoAgent")


    def _format_context_for_prompt(self, context_items: List[ContextItem]) -> str:
        """
        Formats a list of ContextItem objects into a string for the LLM prompt.
        Focuses on text-based content for now. Multi-modal context would require
        different handling (passing objects to agno_agent.run()).
        """
        if not context_items:
            return "No relevant context was provided."

        context_parts = ["Relevant Context:"]
        for item in context_items:
            content_str = str(item.content) # Basic string conversion
            # Consider adding more sophisticated formatting based on item.content_type_description
            # Truncate very long individual context items if necessary
            max_len = 2000 # Max length for a single context item string
            if len(content_str) > max_len:
                content_str = content_str[:max_len] + f"... (truncated, original length {len(content_str)})"
            
            context_parts.append(f"--- Context from Task '{item.source_task_id}' (Goal: {item.source_task_goal[:100]}{'...' if len(item.source_task_goal)>100 else ''}) ---")
            context_parts.append(content_str)
            context_parts.append(f"--- End Context from Task '{item.source_task_id}' ---")
        
        return "\n\n".join(context_parts)

    def _prepare_agno_run_arguments(self, agent_task_input: Union[AgentTaskInput, PlannerInput]) -> str:
        """
        Prepares the user message string for self.agno_agent.arun()
        based on AgentTaskInput or PlannerInput.
        """
        if isinstance(agent_task_input, PlannerInput):
            prompt_parts = [
                f"Overall Objective: {agent_task_input.overall_objective}",
                f"Current Task Goal: {agent_task_input.current_task_goal}"
            ]

            if agent_task_input.parent_task_goal:
                prompt_parts.append(f"Parent Task Goal: {agent_task_input.parent_task_goal}")

            prompt_parts.append(f"Current Planning Depth: {agent_task_input.planning_depth}")

            if agent_task_input.global_constraints_or_preferences:
                constraints_str = "\n  - ".join(agent_task_input.global_constraints_or_preferences)
                prompt_parts.append(f"Global Constraints/Preferences:\n  - {constraints_str}")

            history_context_parts = []
            if agent_task_input.execution_history_and_context:
                h_and_c = agent_task_input.execution_history_and_context
                if h_and_c.prior_sibling_task_outputs:
                    history_context_parts.append("  Prior Sibling Task Outputs:")
                    for item in h_and_c.prior_sibling_task_outputs:
                        history_context_parts.append(f"    - Task: {item.task_goal}, Summary: {item.outcome_summary}")
                if h_and_c.relevant_ancestor_outputs:
                    history_context_parts.append("  Relevant Ancestor Outputs:")
                    for item in h_and_c.relevant_ancestor_outputs:
                        history_context_parts.append(f"    - Task: {item.task_goal}, Summary: {item.outcome_summary}")
                if h_and_c.global_knowledge_base_summary:
                     history_context_parts.append(f"  Global Knowledge Base Summary: {h_and_c.global_knowledge_base_summary}")
            
            if history_context_parts:
                prompt_parts.append("Execution History & Context:")
                prompt_parts.extend(history_context_parts)

            if agent_task_input.replan_request_details:
                replan_parts = ["Re-plan Details (CRITICAL - address this in your new plan):"]
                rd = agent_task_input.replan_request_details
                replan_parts.append(f"  Failed Sub-Goal: {rd.failed_sub_goal}")
                replan_parts.append(f"  Reason for Re-plan: {rd.reason_for_failure_or_replan}")
                if rd.previous_attempt_output_summary:
                    replan_parts.append(f"  Previous Attempt Summary: {rd.previous_attempt_output_summary}")
                if rd.specific_guidance_for_replan:
                    replan_parts.append(f"  Specific Guidance: {rd.specific_guidance_for_replan}")
                prompt_parts.extend(replan_parts)

            prompt_parts.append("\nBased on the 'Current Task Goal' and other provided information, generate a plan to achieve it.")
            
            formatted_user_message_string = "\n\n".join(prompt_parts)
            logger.debug(f"    Adapter '{self.agent_name}': FINAL PROMPT being sent to Agno Agent:\n{formatted_user_message_string}")
            return formatted_user_message_string

        elif isinstance(agent_task_input, AgentTaskInput):
            prompt_template_to_use = INPUT_PROMPT
            if "aggregator" in self.agent_name.lower():
                prompt_template_to_use = AGGREGATOR_PROMPT

            text_context_str = self._format_context_for_prompt(agent_task_input.relevant_context_items)
            overall_goal_for_template = agent_task_input.overall_project_goal or "Not specified"
            
            main_user_message_content = prompt_template_to_use.format(
                input_goal=agent_task_input.current_goal,
                context_str=text_context_str,
                overall_project_goal=overall_goal_for_template
            )
            logger.debug(f"    Adapter '{self.agent_name}': FINAL PROMPT being sent to Agno Agent:\n{main_user_message_content}")
            return main_user_message_content
        
        else:
            raise TypeError(f"Unsupported agent_task_input type: {type(agent_task_input)}")

    async def process(self, node: TaskNode, agent_task_input: Union[AgentTaskInput, PlannerInput]) -> Any: # Changed to async def
        """
        Processes a TaskNode using the configured AgnoAgent.
        """
        logger.info(f"  Adapter '{self.agent_name}': Processing node {node.task_id} (Goal: '{node.goal[:50]}...')")

        user_message_string = self._prepare_agno_run_arguments(agent_task_input)
        
        # Log the detailed message string at debug level
        agno_agent_name = getattr(self.agno_agent, 'name', 'N/A') or 'N/A' # Handle if name is None
        logger.debug(f"    DEBUG: User message string to Agno Agent '{agno_agent_name}':\n{user_message_string}")

        try:
            # Assuming agno_agent has an async method, commonly named arun()
            # If the agno library uses a different name, this needs to be adjusted.
            if not hasattr(self.agno_agent, 'arun'):
                logger.error(f"AgnoAgent instance for '{self.agent_name}' does not have an 'arun' method. Async processing will fail.")
                raise NotImplementedError(f"AgnoAgent for '{self.agent_name}' needs an async 'arun' method.")

            # Step 1: Await arun() to get the RunResponse object
            run_response_obj = await self.agno_agent.arun(user_message_string) 
            
            actual_content_data = None
            if hasattr(run_response_obj, 'content'):
                # Step 2: If RunResponse.content is a coroutine (e.g., an async property), await it.
                if asyncio.iscoroutine(run_response_obj.content):
                    logger.debug(f"    Adapter '{self.agent_name}': run_response_obj.content is a coroutine. Awaiting it.")
                    actual_content_data = await run_response_obj.content
                else:
                    # If RunResponse.content is a direct value after arun() has been awaited.
                    actual_content_data = run_response_obj.content
            else:
                logger.warning(f"    Adapter Warning: Agno agent '{self.agent_name}' RunResponse object has no 'content' attribute for node {node.task_id}.")
            
            if actual_content_data is None:
                 logger.warning(f"    Adapter Warning: Agno agent '{self.agent_name}' resolved content is None for node {node.task_id}.")
            
            return actual_content_data
        except Exception as e:
            logger.exception(f"  Adapter Error: Exception during Agno agent '{self.agent_name}' execution for node {node.task_id}")
            raise
