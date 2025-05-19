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
            logger.warning(f"LlmApiAdapter __init__: agno_agent_instance type is {type(agno_agent_instance)}, not strictly AgnoAgent. Proceeding.")
            # raise ValueError("llm_agent_instance must be an instance of agno.agent.Agent")
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
            # logger.debug(f"    Adapter '{self.agent_name}': FINAL PROMPT being sent to Agno Agent:\n{formatted_user_message_string}") # Keep logging minimal here
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
            # logger.debug(f"    Adapter '{self.agent_name}': FINAL PROMPT being sent to Agno Agent:\n{main_user_message_content}") # Keep logging minimal here
            return main_user_message_content
        
        else:
            raise TypeError(f"Unsupported agent_task_input type: {type(agent_task_input)}")

    async def process(self, node: TaskNode, agent_task_input: Union[AgentTaskInput, PlannerInput]) -> Any: # Changed to async def
        """
        Processes a TaskNode using the configured AgnoAgent.
        Includes a simple retry mechanism for the Agno agent call.
        """
        logger.info(f"  Adapter '{self.agent_name}': Processing node {node.task_id} (Goal: '{node.goal[:50]}...')")

        user_message_string = self._prepare_agno_run_arguments(agent_task_input)
        
        agno_agent_name = getattr(self.agno_agent, 'name', 'N/A') or 'N/A'
        logger.debug(f"    DEBUG: User message string to Agno Agent '{agno_agent_name}':\\n{user_message_string[:200]}...") # Log snippet

        max_retries = 3 # Set to 3 for 1 initial attempt + 2 retries
        retry_delay_seconds = 5 

        for attempt in range(max_retries):
            try:
                if not hasattr(self.agno_agent, 'arun'):
                    logger.error(f"AgnoAgent instance for '{self.agent_name}' does not have an 'arun' method.")
                    raise NotImplementedError(f"AgnoAgent for '{self.agent_name}' needs an async 'arun' method.")

                logger.debug(f"    Adapter '{self.agent_name}': About to call await self.agno_agent.arun() (Attempt {attempt + 1}/{max_retries})")
                run_response_obj = await self.agno_agent.arun(user_message_string) 
                logger.debug(f"    Adapter '{self.agent_name}': After await self.agno_agent.arun(), run_response_obj type: {type(run_response_obj)}")
                
                actual_content_data = None
                if hasattr(run_response_obj, 'content'):
                    content_attr = run_response_obj.content
                    logger.debug(f"    Adapter '{self.agent_name}': run_response_obj.content exists. Type of content_attr: {type(content_attr)}")

                    if asyncio.iscoroutine(content_attr):
                        logger.info(f"    Adapter '{self.agent_name}': content_attr IS a coroutine. Awaiting it now.")
                        actual_content_data = await content_attr
                        logger.debug(f"    Adapter '{self.agent_name}': After awaiting content_attr, actual_content_data type: {type(actual_content_data)}")
                    else:
                        logger.info(f"    Adapter '{self.agent_name}': content_attr is NOT a coroutine. Using its value directly.")
                        actual_content_data = content_attr
                else:
                    logger.warning(f"    Adapter Warning: Agno agent '{self.agent_name}' RunResponse object has no 'content' attribute for node {node.task_id} (Attempt {attempt + 1}).")
                
                # Specific adapters (like PlannerAdapter) are responsible for checking if actual_content_data is None
                # and raising an error if None is not acceptable for them.
                # This retry loop is primarily for exceptions during arun() or if arun() itself indicates
                # a retryable issue, not specifically for None content if None is a possible 
                # (though perhaps unhelpful) outcome for some agents.
                
                logger.info(f"    Adapter '{self.agent_name}': Successfully processed (Attempt {attempt+1}). Type of actual_content_data: {type(actual_content_data)}. Is it a coroutine? {asyncio.iscoroutine(actual_content_data)}")
                return actual_content_data # Success, return the content
            
            except Exception as e:
                logger.warning(f"  Adapter Error (Attempt {attempt + 1}/{max_retries}): Exception during Agno agent '{self.agent_name}' execution for node {node.task_id}: {e}")
                if attempt < max_retries - 1:
                    logger.info(f"    Retrying in {retry_delay_seconds} seconds...")
                    await asyncio.sleep(retry_delay_seconds)
                else:
                    logger.error(f"  Adapter Error: Max retries ({max_retries}) reached for Agno agent '{self.agent_name}' on node {node.task_id}. Re-raising last exception.")
                    raise # Re-raise the last exception after max retries
        
        # This line should ideally not be reached if max_retries > 0 due to the 'raise' in the except block.
        # However, as a fallback, and to satisfy linters/type checkers that expect a return value.
        logger.error(f"  Adapter Error: Loop completed without successful return or re-raising exception for node {node.task_id}. This indicates an issue in retry logic.")
        return None
