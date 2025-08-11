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
from json_repair import repair_json
from agno.agent import Agent as AgnoAgent

from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode # For type hinting
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import (
    ContextItem, PlanOutput, AtomizerOutput, AgentTaskInput, PlannerInput, ExecutionHistoryItem,
    PlanModifierInput # Added PlanModifierInput
)

# FIX: Import NodeType from types module
from sentientresearchagent.hierarchical_agent_framework.types import NodeType

# Import prompt templates
from .prompts import INPUT_PROMPT, AGGREGATOR_PROMPT

from sentientresearchagent.exceptions import (
    AgentExecutionError, AgentTimeoutError, AgentRateLimitError,
    handle_exception, create_error_context
)
# Lazy import to avoid circular import
# from sentientresearchagent.core.error_handler import handle_agent_errors, ErrorRecovery
# Lazy import to avoid circular import
# from sentientresearchagent.core.cache.decorators import cache_agent_response, cache_get, cache_set

from ..tracing.manager import TraceManager

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
    async def process(self, node: TaskNode, agent_task_input: Any, trace_manager: "TraceManager") -> Any: # Changed to async def
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
            
            context_parts.append(f"--- Context from Task '{item.source_task_id}' (Goal: {item.source_task_goal}) ---")
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

    async def _extract_and_parse_json(self, text: str, response_model: Type[OutputType]) -> Optional[OutputType]:
        """
        Extracts a JSON object from a string and parses it into the response model.
        Uses the comprehensive OutputFixingParser with progressive strategies including LLM-based fixing.
        """
        logger.critical("🚀🚀🚀 RUNNING COMPREHENSIVE OUTPUT FIXING PARSER 🚀🚀🚀")
        logger.debug(f"Attempting to parse JSON from raw text (length: {len(text)}) for model {response_model.__name__}")

        try:
            # Import and use the OutputFixingParser from utils
            from .utils import get_global_output_parser
            
            # Get the global parser instance 
            output_parser = get_global_output_parser(max_previous_attempts_in_context=2)
            
            # Use the comprehensive parser with all strategies including LLM fixing
            result = await output_parser.parse(
                text=text,
                response_model=response_model,
                use_llm_fixing=True,  # Enable LLM-based fixing as last resort
                original_error="Failed to parse LLM output with standard JSON parsing"
            )
            
            if result:
                logger.info(f"✅ OutputFixingParser successfully parsed {response_model.__name__}")
                return result
            else:
                logger.error(f"❌ OutputFixingParser failed to parse {response_model.__name__} from text")
                return None
                
        except Exception as e:
            logger.error(f"OutputFixingParser encountered error: {e}")
            logger.error(f"Falling back to None for {response_model.__name__}")
            return None

    # @handle_agent_errors(agent_name_param="self.agent_name", component="llm_adapter") # Removed to avoid circular import
    # @cache_agent_response(ttl_seconds=3600) # Removed to avoid circular import
    async def process(self, node: TaskNode, agent_task_input: InputType, trace_manager: "TraceManager") -> OutputType:
        """
        Processes a TaskNode using the configured AgnoAgent with caching and improved error handling.
        """
        logger.info(f"  Adapter '{self.agent_name}': Processing node {node.task_id} (Goal: '{node.goal[:50]}...')")

        # Determine the stage name based on adapter type
        stage_name = self._get_stage_name(node)
        
        # Log the stage name for debugging
        logger.debug(f"  Adapter '{self.agent_name}': Using stage name '{stage_name}' for node {node.task_id} (status: {node.status})")
        
        # CRITICAL FIX: Don't create new stage, just update existing one
        # The node handlers should already have created the stage
        trace = trace_manager.get_trace_for_node(node.task_id)
        if not trace:
            logger.warning(f"No trace found for node {node.task_id}, creating one")
            trace = trace_manager.create_trace(node.task_id, node.goal)
        
        # Find existing stage or create if not exists
        existing_stage = trace.get_stage(stage_name)
        if not existing_stage:
            logger.info(f"Creating new {stage_name} stage for node {node.task_id}")
            stage = trace_manager.start_stage(
                node_id=node.task_id,
                stage_name=stage_name,
                agent_name=self.agent_name,
                adapter_name=self.__class__.__name__
            )
        else:
            logger.info(f"Updating existing {stage_name} stage for node {node.task_id}")
            stage = existing_stage

        # Capture model information before processing
        model_info = self._get_model_info()
        
        # Store model info in node's aux_data
        node.aux_data.setdefault("execution_details", {})
        node.aux_data["execution_details"]["model_info"] = model_info
        node.aux_data["execution_details"]["processing_started"] = datetime.now().isoformat()

        # Get system prompt
        system_prompt = getattr(self.agno_agent, 'system_message', None) or getattr(self.agno_agent, 'system_prompt', None)
        if system_prompt:
            node.aux_data["execution_details"]["system_prompt"] = system_prompt

        try:
            user_message_string = self._prepare_agno_run_arguments(agent_task_input)
            
            # Store the final formatted input for frontend display and tracing
            node.aux_data["execution_details"]["final_llm_input"] = user_message_string
            
            # Build complete LLM messages array
            llm_messages = []
            if system_prompt:
                llm_messages.append({"role": "system", "content": system_prompt})
            llm_messages.append({"role": "user", "content": user_message_string})
            
            # CRITICAL FIX: Update trace stage with all LLM interaction data
            trace_manager.update_stage(
                node_id=node.task_id,
                stage_name=stage_name,
                agent_name=self.agent_name,
                adapter_name=self.__class__.__name__,
                model_info=model_info,
                system_prompt=system_prompt,
                user_input=user_message_string,
                input_context={
                    "agent_task_input": agent_task_input.model_dump(),
                    "formatted_input_length": len(user_message_string),
                    "task_type": str(node.task_type),
                    "node_type": str(node.node_type),
                    "context_items_count": len(agent_task_input.relevant_context_items),
                    "has_dependency_context": any(item.content_type_description == "explicit_dependency_output" for item in agent_task_input.relevant_context_items)
                },
                processing_parameters={
                    "temperature": getattr(self.agno_agent, 'temperature', None),
                    "max_tokens": getattr(self.agno_agent, 'max_tokens', None),
                    "model": getattr(self.agno_agent, 'model', None)
                },
                llm_input_messages=llm_messages,
                llm_input_length=sum(len(msg["content"]) for msg in llm_messages)
            )
            
        except Exception as e:
            trace_manager.complete_stage(
                node_id=node.task_id,
                stage_name=stage_name,
                error=str(e)
            )
            raise AgentExecutionError(
                agent_name=self.agent_name,
                task_id=node.task_id,
                original_error=e,
                attempt_number=1
            )

        # Execute agent with proper response capture
        async def execute_agent():
            # Get stage name in local scope to avoid closure issues
            local_stage_name = self._get_stage_name(node)
            
            if not hasattr(self.agno_agent, 'arun'):
                raise AgentExecutionError(
                    agent_name=self.agent_name,
                    task_id=node.task_id,
                    original_error=NotImplementedError(f"AgnoAgent for '{self.agent_name}' needs an async 'arun' method."),
                    attempt_number=1
                )

            try:
                # Time the LLM call
                llm_start_time = asyncio.get_event_loop().time()
                logger.info(f"🚀 LLM CALL START: {self.agent_name} for node {node.task_id}")
                
                run_response_obj = await self.agno_agent.arun(user_message_string)
                
                llm_end_time = asyncio.get_event_loop().time()
                llm_duration = llm_end_time - llm_start_time
                logger.info(f"✅ LLM CALL COMPLETE: {self.agent_name} for node {node.task_id} - Duration: {llm_duration:.2f}s")
                
                # Store timing in trace
                if trace_manager:
                    trace_manager.update_stage(
                        node_id=node.task_id,
                        stage_name=local_stage_name,
                        llm_call_duration_seconds=llm_duration,
                        llm_call_start_time=llm_start_time,
                        llm_call_end_time=llm_end_time
                    )
                
                actual_content_data = None
                raw_response = None
                
                if hasattr(run_response_obj, 'content'):
                    content_attr = run_response_obj.content
                    
                    if asyncio.iscoroutine(content_attr):
                        actual_content_data = await content_attr
                    else:
                        actual_content_data = content_attr
                        
                    # Store raw response for tracing - NO TRUNCATION for aggregation or execution
                    if local_stage_name in ['aggregation', 'execution']:
                        # For aggregation and execution, store the COMPLETE response - this is what users need to see
                        raw_response = str(actual_content_data)
                        logger.info(f"🔍 {local_stage_name.upper()}: Storing FULL response ({len(raw_response)} characters) for tracing")
                    else:
                        # For other stages (planning, atomization), limit to prevent memory issues
                        full_response = str(actual_content_data)
                        if len(full_response) > 5000:  # Increased from 2000 to 5000 for better debugging
                            raw_response = full_response[:5000] + f"... [Response truncated from {len(full_response)} characters for memory efficiency]"
                            logger.info(f"🔍 {local_stage_name.upper()}: Truncated response from {len(full_response)} to 5000 characters for tracing")
                        else:
                            raw_response = full_response
                            logger.info(f"🔍 {local_stage_name.upper()}: Storing full response ({len(raw_response)} characters) for tracing")
                else:
                    logger.warning(f"Agno agent '{self.agent_name}' RunResponse object has no 'content' attribute for node {node.task_id}.")
                
                # CRITICAL FIX: Update trace stage with LLM response
                if raw_response:
                    trace_manager.update_stage(
                        node_id=node.task_id,
                        stage_name=local_stage_name,
                        llm_response=raw_response
                    )
                
                # Handle structured output parsing if needed
                if self.agno_agent.response_model and isinstance(actual_content_data, str):
                    parsed_data = self._extract_and_parse_json(actual_content_data, self.agno_agent.response_model)
                    if parsed_data:
                        actual_content_data = parsed_data

                logger.info(f"Adapter '{self.agent_name}': Successfully processed. Type of actual_content_data: {type(actual_content_data)}")
                return actual_content_data
                
            except Exception as e:
                # Handle specific error types
                if "rate limit" in str(e).lower() or "429" in str(e):
                    raise AgentRateLimitError(agent_name=self.agent_name)
                elif "timeout" in str(e).lower():
                    raise AgentTimeoutError(agent_name=self.agent_name, task_id=node.task_id, timeout_seconds=30.0)
                else:
                    raise AgentExecutionError(agent_name=self.agent_name, task_id=node.task_id, original_error=e, attempt_number=1)

        try:
            # Lazy import to avoid circular import
            from sentientresearchagent.core.error_handler import ErrorRecovery
            result = await ErrorRecovery.retry_with_backoff(
                func=execute_agent,
                max_retries=3,
                base_delay=2.0,
                exceptions=(AgentRateLimitError, AgentTimeoutError, AgentExecutionError)
            )
            
            # Update execution details with completion info
            node.aux_data["execution_details"]["processing_completed"] = datetime.now().isoformat()
            node.aux_data["execution_details"]["success"] = True
            
            # CRITICAL FIX: Complete tracing stage with rich output data - NO TRUNCATION for aggregation or execution
            stage_name = self._get_stage_name(node)
            if stage_name in ['aggregation', 'execution']:
                # For aggregation and execution, store the COMPLETE result - this is what users need
                output_data = str(result) if result else "No output"
                logger.info(f"🔍 {stage_name.upper()}: Storing COMPLETE output data ({len(output_data)} characters) for tracing")
            else:
                # For other stages (planning, atomization), use reasonable summary
                if result:
                    full_output = str(result)
                    if len(full_output) > 2000:  # Reasonable limit for non-execution stages
                        output_data = full_output[:2000] + f"... [Output truncated from {len(full_output)} characters]"
                    else:
                        output_data = full_output
                else:
                    output_data = "No output"
                logger.info(f"🔍 {stage_name.upper()}: Storing output data ({len(output_data)} characters) for tracing")

            trace_manager.complete_stage(
                node_id=node.task_id,
                stage_name=stage_name,
                output_data=output_data
            )
            
            return result
            
        except Exception as e:
            # Update execution details with error info
            node.aux_data["execution_details"]["processing_completed"] = datetime.now().isoformat()
            node.aux_data["execution_details"]["success"] = False
            node.aux_data["execution_details"]["error"] = str(e)
            
            # Complete tracing stage with error
            trace_manager.complete_stage(
                node_id=node.task_id,
                stage_name=stage_name,
                error=str(e)
            )
            
            raise

    def _get_stage_name(self, node: Optional[TaskNode] = None) -> str:
        """
        Determine the stage name based on adapter type AND node status.
        
        Args:
            node: Optional TaskNode to consider for status-based stage determination
        """
        class_name = self.__class__.__name__.lower()
        
        # CRITICAL FIX: Consider node status when determining stage
        if node and hasattr(node, 'status'):
            from sentientresearchagent.hierarchical_agent_framework.types import TaskStatus
            
            # If node is AGGREGATING, it should be aggregation stage regardless of adapter
            if node.status == TaskStatus.AGGREGATING:
                return 'aggregation'
            
            # If node is NOT aggregating but adapter is an aggregator, this is wrong
            if 'aggregator' in class_name and node.status in [TaskStatus.READY, TaskStatus.RUNNING]:
                logger.warning(
                    f"🚨 ADAPTER MISMATCH: Node {node.task_id} (status: {node.status}) "
                    f"is using aggregator adapter '{self.__class__.__name__}' but not in AGGREGATING status!"
                )
                # Force to execution stage to prevent confusion
                return 'execution'
        
        # Default behavior based on adapter type
        if 'planner' in class_name:
            return 'planning'
        elif 'executor' in class_name:
            return 'execution'
        elif 'aggregator' in class_name:
            return 'aggregation'
        elif 'atomizer' in class_name:
            return 'atomization'
        elif 'customsearch' in class_name or 'search' in class_name:
            # EXPLICIT: All search adapters should NEVER do aggregation
            return 'execution'
        else:
            # Default to processing, but log a warning
            logger.warning(f"🚨 Unknown adapter type '{self.__class__.__name__}' - defaulting to 'processing' stage")
            return 'processing'

    def close(self):
        """Closes the underlying Agno agent's resources."""
        if hasattr(self.agno_agent, 'close') and callable(self.agno_agent.close):
            logger.info(f"  Adapter '{self.agent_name}': Closing underlying Agno agent.")
            self.agno_agent.close()