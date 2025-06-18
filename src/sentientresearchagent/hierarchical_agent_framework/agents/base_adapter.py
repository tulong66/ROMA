from abc import ABC, abstractmethod
from typing import Dict, Any, Union, List, TypeVar, Generic, Type, Optional
from loguru import logger # Add this
from agno.agent import Agent as AgnoAgent # Renaming to avoid conflict if we define our own Agent interface
# It's good practice to also import the async version if available and distinct
# from agno.agent import AsyncAgent as AsyncAgnoAgent # Assuming such an import exists for type hinting
import asyncio # Add this import
from datetime import datetime
import inspect
import re
import json

from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode # For type hinting
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import (
    ContextItem, PlanOutput, AtomizerOutput, AgentTaskInput, PlannerInput, ExecutionHistoryItem,
    PlanModifierInput # Added PlanModifierInput
)

# Import prompt templates
from .prompts import INPUT_PROMPT, AGGREGATOR_PROMPT

from sentientresearchagent.exceptions import (
    AgentExecutionError, AgentTimeoutError, AgentRateLimitError,
    handle_exception, create_error_context
)
from sentientresearchagent.core.error_handler import handle_agent_errors, ErrorRecovery
from sentientresearchagent.core.cache.decorators import cache_agent_response, cache_get, cache_set

InputType = TypeVar('InputType')
OutputType = TypeVar('OutputType')

class BaseAdapter(ABC):
    """
    Abstract base class for all agent adapters in this framework.
    An adapter is responsible for interfacing between the framework's
    TaskNode/context and a specific agent implementation (e.g., an AgnoAgent).
    """
    def __init__(self, agent_name: str = "BaseAdapter"):
        """
        Initializes the adapter with a name.
        
        Args:
            agent_name: A descriptive name for logging and identification.
        """
        self.agent_name = agent_name

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

class LlmApiAdapter(BaseAdapter, Generic[InputType, OutputType]):
    """
    Base adapter for agents implemented using the Agno library.
    This adapter simplifies interaction by leveraging Agno's native
    structured output and tool handling.
    """
    def __init__(self, agno_agent_instance: AgnoAgent, agent_name: str = "LlmApiAdapter"):
        """
        Args:
            agno_agent_instance: The instantiated AgnoAgent.
            agent_name: A descriptive name for logging.
        """
        super().__init__(agent_name)
        if not agno_agent_instance:
            raise ValueError(f"{agent_name} requires a valid AgnoAgent instance.")
        self.agno_agent = agno_agent_instance

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

    def _get_task_specific_instructions(self, task_type: str) -> str:
        """Get specific instructions based on task type."""
        instructions = {
            "PLAN": "Generate a detailed plan with sub-tasks. Each sub-task should have a clear goal, appropriate task_type, and node_type.",
            "WRITE": "Write comprehensive, well-structured content that addresses the goal. Include relevant examples and citations when appropriate.",
            "SEARCH": "Conduct thorough research using available tools. Provide detailed findings with sources and verification.",
            "THINK": "Perform deep analysis and reasoning. Present logical conclusions with supporting evidence.",
            "AGGREGATE": "Synthesize information from all provided sources into a coherent summary. Highlight key insights and connections."
        }
        return instructions.get(task_type.upper(), "Complete the task according to the specified goal and requirements.")

    def _prepare_agno_run_arguments(self, agent_task_input: InputType) -> str:
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
            # 🔥 USE THE ENHANCED FORMATTED CONTEXT!
            if hasattr(agent_task_input, 'formatted_full_context') and agent_task_input.formatted_full_context:
                # Use the new enhanced hierarchical context
                logger.info(f"🔥 Using enhanced hierarchical context for {self.agent_name}")
                
                prompt_template_to_use = INPUT_PROMPT
                if "aggregator" in self.agent_name.lower():
                    prompt_template_to_use = AGGREGATOR_PROMPT

                overall_goal_for_template = agent_task_input.overall_project_goal or "Not specified"
                
                main_user_message_content = prompt_template_to_use.format(
                    input_goal=agent_task_input.current_goal,
                    context_str=agent_task_input.formatted_full_context,  # 🔥 USE THE NEW CONTEXT!
                    overall_project_goal=overall_goal_for_template
                )
            else:
                # Fallback to old method if no enhanced context
                logger.info(f"🔥 Falling back to old context method for {self.agent_name}")
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
            
            return main_user_message_content
        
        elif isinstance(agent_task_input, PlanModifierInput):
            try:
                original_plan_json_str = agent_task_input.original_plan.model_dump_json(indent=2)
            except Exception as e:
                logger.error(f"Error serializing original_plan to JSON for PlanModifierInput: {e}")
                original_plan_json_str = str(agent_task_input.original_plan.model_dump())

            prompt_content = f"""Overall Objective:
{agent_task_input.overall_objective}

Original Plan JSON:
{original_plan_json_str}

User Modification Instructions:
{agent_task_input.user_modification_instructions}

Based on the 'User Modification Instructions', revise the 'Original Plan JSON' to better achieve the 'Overall Objective'.
Ensure your output is a valid JSON conforming to the PlanOutput schema, containing a list of sub-tasks.
"""
            logger.debug(f"    Adapter '{self.agent_name}': PlanModifierInput prompt prepared.")
            return prompt_content
        
        else:
            raise TypeError(f"Unsupported agent_task_input type: {type(agent_task_input)} for _prepare_agno_run_arguments")

    def _get_model_info(self) -> Dict[str, Any]:
        """Extract model information from the AgnoAgent."""
        model_info = {
            "adapter_name": self.agent_name,
            "model_provider": "unknown",
            "model_name": "unknown",
            "model_id": "unknown"
        }
        
        try:
            if hasattr(self.agno_agent, 'model') and self.agno_agent.model:
                model = self.agno_agent.model
                
                # Try multiple approaches to get model information
                model_id = None
                
                # Method 1: Direct model.id
                if hasattr(model, 'id') and model.id:
                    model_id = model.id
                    
                # Method 2: Model name attribute  
                elif hasattr(model, 'name') and model.name:
                    model_id = model.name
                    
                # Method 3: Check if it's a LiteLLM model with model attribute
                elif hasattr(model, 'model') and model.model:
                    model_id = model.model
                    
                # Method 4: Check for _model attribute (some LiteLLM versions)
                elif hasattr(model, '_model') and model._model:
                    model_id = model._model
                    
                # Method 5: Look in model configuration/args
                elif hasattr(model, '__dict__'):
                    for attr in ['model', '_model', 'model_name', 'engine']:
                        if hasattr(model, attr):
                            val = getattr(model, attr)
                            if val and isinstance(val, str) and val not in ['unknown', '']:
                                model_id = val
                                break
                
                if model_id:
                    model_info["model_id"] = model_id
                    
                    # Parse model ID for provider and name
                    if "/" in model_id:
                        # Format like "openrouter/anthropic/claude-3-sonnet" or "anthropic/claude-3-sonnet"
                        parts = model_id.split("/")
                        if len(parts) >= 2:
                            # If it looks like provider/model or provider/company/model
                            if parts[0] in ['openrouter', 'anthropic', 'openai', 'google', 'cohere', 'mistral']:
                                model_info["model_provider"] = parts[0]
                                model_info["model_name"] = "/".join(parts[1:])
                            else:
                                # Assume first part is provider, rest is model
                                model_info["model_provider"] = parts[0]  
                                model_info["model_name"] = "/".join(parts[1:])
                    else:
                        # No slash - could be direct model name like "gpt-4", "claude-3-sonnet-20241022"
                        model_info["model_name"] = model_id
                        
                        # Infer provider from model name
                        if model_id.startswith(('gpt-', 'text-', 'davinci', 'o1-')):
                            model_info["model_provider"] = "openai"
                        elif model_id.startswith(('claude-', 'claude')):
                            model_info["model_provider"] = "anthropic"
                        elif model_id.startswith(('gemini-', 'palm-')):
                            model_info["model_provider"] = "google"
                        elif model_id.startswith(('command-', 'embed-')):
                            model_info["model_provider"] = "cohere"
                        elif model_id.startswith(('mistral-', 'mixtral-')):
                            model_info["model_provider"] = "mistral"
                        else:
                            model_info["model_provider"] = "unknown"
                            
        except Exception as e:
            logger.debug(f"Could not extract model info from agent {self.agent_name}: {e}")
            
        return model_info

    def _extract_and_parse_json(self, text: str, response_model: Type[OutputType]) -> Optional[OutputType]:
        """
        Extracts a JSON object from a string and parses it into the response model.
        This is a robust version that handles JSON in markdown, with surrounding text, or as a substring.
        """
        logger.critical("🚀🚀🚀 RUNNING FINAL ROBUST JSON PARSER 🚀🚀🚀")
        logger.debug(f"Attempting to extract JSON from raw text (length: {len(text)}) for model {response_model.__name__}")

        # Strategy 1: Look for JSON within a markdown code block (most reliable)
        match = re.search(r"```(?:json)?\s*([\[\{].*?[\]\}])\s*```", text, re.DOTALL)
        if match:
            json_str = match.group(1).strip()
            logger.info("Strategy 1: Found JSON in markdown block.")
            try:
                return response_model.model_validate_json(json_str)
            except Exception as e:
                logger.warning(f"Strategy 1 failed: Could not parse JSON from markdown block. Error: {e}")

        # Strategy 2: Find the largest possible JSON blob from the first to last bracket
        json_str = None
        first_bracket = min(
            (text.find('{') if text.find('{') != -1 else float('inf')),
            (text.find('[') if text.find('[') != -1 else float('inf'))
        )
        if first_bracket != float('inf'):
            last_bracket = max(text.rfind('}'), text.rfind(']'))
            if last_bracket > first_bracket:
                json_str = text[first_bracket:last_bracket+1].strip()
                logger.info("Strategy 2: Found potential JSON blob from first to last bracket.")
                try:
                    return response_model.model_validate_json(json_str)
                except Exception as e:
                    logger.warning(f"Strategy 2 failed: Could not parse broad JSON blob. Error: {e}")

        # Strategy 3: Use JSONDecoder to find the first valid JSON object in the string
        logger.info("Strategy 3: Attempting to find first valid JSON object in the string.")
        try:
            obj, _ = json.JSONDecoder().raw_decode(text.strip())
            json_str = json.dumps(obj)
            return response_model.model_validate_json(json_str)
        except (json.JSONDecodeError, TypeError, AttributeError) as e:
            logger.warning(f"Strategy 3 failed: JSONDecoder could not find a valid object. Error: {e}")

        logger.error(f"All strategies failed. Could not extract or parse a valid JSON for {response_model.__name__} from the text.")
        return None

    @handle_agent_errors(agent_name_param="self.agent_name", component="llm_adapter")
    @cache_agent_response(ttl_seconds=3600)
    async def process(self, node: TaskNode, agent_task_input: InputType) -> OutputType:
        """
        Processes a TaskNode using the configured AgnoAgent with caching and improved error handling.
        """
        logger.info(f"  Adapter '{self.agent_name}': Processing node {node.task_id} (Goal: '{node.goal[:50]}...')")

        # Capture model information before processing
        model_info = self._get_model_info()
        
        # Store model info in node's aux_data
        node.aux_data.setdefault("execution_details", {})
        node.aux_data["execution_details"]["model_info"] = model_info
        node.aux_data["execution_details"]["processing_started"] = datetime.now().isoformat()

        # NEW: Store system prompt if available
        system_prompt = getattr(self.agno_agent, 'system_message', None) or getattr(self.agno_agent, 'system_prompt', None)
        if system_prompt:
            node.aux_data["execution_details"]["system_prompt"] = system_prompt

        # Check if we should skip cache for this request
        if hasattr(agent_task_input, 'force_refresh') and agent_task_input.force_refresh:
            logger.debug(f"  Adapter '{self.agent_name}': Skipping cache due to force_refresh flag")
        
        try:
            user_message_string = self._prepare_agno_run_arguments(agent_task_input)
            
            # Store the final formatted input for frontend display
            node.aux_data["execution_details"]["final_llm_input"] = user_message_string
            
        except Exception as e:
            raise AgentExecutionError(
                agent_name=self.agent_name,
                task_id=node.task_id,
                original_error=e,
                attempt_number=1
            )
        
        agno_agent_name = getattr(self.agno_agent, 'name', 'N/A') or 'N/A'
        logger.debug(f"    DEBUG: User message string to Agno Agent '{agno_agent_name}':\\n{user_message_string[:200]}...")

        # Use the retry utility instead of manual retry logic
        async def execute_agent():
            if not hasattr(self.agno_agent, 'arun'):
                raise AgentExecutionError(
                    agent_name=self.agent_name,
                    task_id=node.task_id,
                    original_error=NotImplementedError(f"AgnoAgent for '{self.agent_name}' needs an async 'arun' method."),
                    attempt_number=1
                )

            try:
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
                    logger.warning(f"    Adapter Warning: Agno agent '{self.agent_name}' RunResponse object has no 'content' attribute for node {node.task_id}.")
                
                # If a response model is expected but we got a string, try to parse it.
                if self.agno_agent.response_model and isinstance(actual_content_data, str):
                    logger.warning(f"    Adapter '{self.agent_name}': Expected a structured object but got a string. Attempting to extract and parse JSON.")
                    
                    parsed_data = self._extract_and_parse_json(actual_content_data, self.agno_agent.response_model)

                    if parsed_data:
                        logger.info(f"    Adapter '{self.agent_name}': Successfully extracted and parsed JSON.")
                        actual_content_data = parsed_data
                    else:
                        logger.error(f"    Adapter '{self.agent_name}': Failed to recover structured data from string response.")
                        # Keep actual_content_data as string so downstream can see the raw output

                # Check if response_model was set and if content is None
                if self.agno_agent.response_model is not None and actual_content_data is None:
                    raise AgentExecutionError(
                        agent_name=self.agent_name,
                        task_id=node.task_id,
                        original_error=ValueError(
                            f"Agno agent '{self.agent_name}' with response_model "
                            f"'{self.agno_agent.response_model.__name__}' returned None."
                        ),
                        attempt_number=1
                    )

                logger.info(f"    Adapter '{self.agent_name}': Successfully processed. Type of actual_content_data: {type(actual_content_data)}")
                return actual_content_data
                
            except Exception as e:
                # Handle specific error types
                if "rate limit" in str(e).lower() or "429" in str(e):
                    raise AgentRateLimitError(agent_name=self.agent_name)
                elif "timeout" in str(e).lower():
                    raise AgentTimeoutError(
                        agent_name=self.agent_name, 
                        task_id=node.task_id, 
                        timeout_seconds=30.0
                    )
                else:
                    raise AgentExecutionError(
                        agent_name=self.agent_name,
                        task_id=node.task_id,
                        original_error=e,
                        attempt_number=1
                    )

        # Use ErrorRecovery for retry logic with better error handling
        try:
            result = await ErrorRecovery.retry_with_backoff(
                func=execute_agent,
                max_retries=3,
                base_delay=5.0,
                exceptions=(AgentRateLimitError, AgentTimeoutError, AgentExecutionError)
            )
            
            # Update execution details with completion info
            node.aux_data["execution_details"]["processing_completed"] = datetime.now().isoformat()
            node.aux_data["execution_details"]["success"] = True
            
            # Cache result manually with additional metadata if needed
            cache_set(
                namespace="agent_responses", 
                identifier=f"{self.agent_name}:{node.task_id}",
                value=result,
                context={"task_type": str(node.task_type), "node_type": str(node.node_type)},
                ttl_seconds=3600
            )
            
            return result
            
        except Exception as e:
            # Update execution details with error info
            node.aux_data["execution_details"]["processing_completed"] = datetime.now().isoformat()
            node.aux_data["execution_details"]["success"] = False
            node.aux_data["execution_details"]["error"] = str(e)
            
            # Final error handling - convert any remaining exceptions
            raise handle_exception(
                e, 
                task_id=node.task_id, 
                agent_name=self.agent_name,
                context=create_error_context(
                    task_goal=node.goal,
                    task_type=node.task_type,
                    node_type=node.node_type
                )
            )

    def close(self):
        """Closes the underlying Agno agent's resources."""
        if hasattr(self.agno_agent, 'close') and callable(self.agno_agent.close):
            logger.info(f"  Adapter '{self.agent_name}': Closing underlying Agno agent.")
            self.agno_agent.close()
