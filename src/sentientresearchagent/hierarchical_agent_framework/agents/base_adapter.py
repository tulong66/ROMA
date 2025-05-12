from abc import ABC, abstractmethod
from typing import Dict, Any, Union, List
from agno.agent import Agent as AgnoAgent # Renaming to avoid conflict if we define our own Agent interface
from agno.client import RunResponse # To type hint the response from agno_agent.run()

from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode # For type hinting
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import ContextItem, PlanOutput, AtomizerOutput # For type hinting results

# Import prompt templates
from .prompts import INPUT_PROMPT, AGGREGATOR_PROMPT

# Basic console coloring for logs, can be replaced with a proper logger
def colored(text, color):
    colors = {"green": "\033[92m", "cyan": "\033[96m", "yellow": "\033[93m", "red": "\033[91m", "bold": "\033[1m", "end": "\033[0m"}
    return f"{colors.get(color, '')}{text}{colors['end']}"

class BaseAdapter(ABC):
    """
    Abstract base class for all agent adapters in this framework.
    An adapter is responsible for interfacing between the framework's
    TaskNode/context and a specific agent implementation (e.g., an AgnoAgent).
    """
    @abstractmethod
    def process(self, node: TaskNode, agent_task_input: Any) -> Any:
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
    def __init__(self, agno_agent_instance: AgnoAgent, agent_name: str = "UnnamedAgnoAgent"):
        """
        Args:
            agno_agent_instance: The instantiated AgnoAgent.
            agent_name: A descriptive name for logging.
        """
        if not isinstance(agno_agent_instance, AgnoAgent):
            raise ValueError("llm_agent_instance must be an instance of agno.agent.Agent")
        self.agno_agent = agno_agent_instance
        self.agent_name = agent_name if agent_name else (agno_agent_instance.name or "UnnamedAgnoAgent")


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

    def _prepare_agno_run_arguments(self, agent_task_input: Any) -> Dict[str, Any]:
        """
        Prepares the arguments for self.agno_agent.run() based on AgentTaskInput.
        This method will be expanded for multi-modal inputs.
        For now, it focuses on constructing the main prompt string.

        Args:
            agent_task_input: An instance of AgentTaskInput.

        Returns:
            A dictionary of arguments for agno_agent.run().
        """
        # Determine which prompt template to use based on adapter type
        # This is a bit of a hack; ideally, the prompt template choice
        # might be more configurable or specific to the agent's role.
        prompt_template_to_use = INPUT_PROMPT # Default
        if "aggregator" in self.agent_name.lower(): # Simple heuristic
            prompt_template_to_use = AGGREGATOR_PROMPT

        # Format text-based context for the prompt string
        # Multi-modal context items would be passed directly as arguments (e.g., images=..., audio=...)
        text_context_str = self._format_context_for_prompt(agent_task_input.relevant_context_items)
        
        # Construct the main prompt string
        # Note: agno.Agent's system_message provides the core instructions.
        # This input prompt provides the dynamic data (goal, context).
        main_prompt_content = prompt_template_to_use.format(
            input_goal=agent_task_input.current_goal,
            context_str=text_context_str
        )
        
        run_args = {
            "prompt": main_prompt_content, # Agno expects the main user input as 'prompt' or the first arg
            # "stream": False, # Default is False, explicitly set if needed
            # Add other agno.run() parameters here if needed, e.g.:
            # "images": [img_obj for img_obj in prepared_multimodal_inputs if type(img_obj) is AgnoImage],
        }
        return run_args

    def process(self, node: TaskNode, agent_task_input: Any) -> Any:
        """
        Processes a TaskNode using the configured AgnoAgent.

        Args:
            node: The TaskNode to process.
            agent_task_input: An AgentTaskInput object.

        Returns:
            The content from the Agno RunResponse (e.g., a Pydantic model instance, string).
        """
        print(colored(f"  Adapter '{self.agent_name}': Processing node {node.task_id} (Goal: '{node.goal[:50]}...')", "cyan"))

        run_arguments = self._prepare_agno_run_arguments(agent_task_input)
        
        # For debugging, print the prompt being sent (or part of it)
        # print(colored(f"    To Agno Agent '{self.agno_agent.name or 'N/A'}': Prompt: {str(run_arguments.get('prompt'))[:200]}...", "grey"))

        try:
            # AgnoAgent.run() handles structured output if 'response_model' was set on the agent.
            # It also handles the tool execution loop internally if tools were provided to the agent.
            response: RunResponse = self.agno_agent.run(**run_arguments)
            
            # print(colored(f"    Adapter '{self.agent_name}': Received RunResponse. Content type: {response.content_type}", "cyan"))
            # pprint.pprint(response) # For deep debugging of the full RunResponse

            # The primary result is in response.content
            # If response_model was used, response.content is the Pydantic object.
            # Otherwise, it's typically a string.
            # Multi-modal outputs would be in response.images, response.audio etc. (to be handled later)
            
            if response.content is None:
                 print(colored(f"    Adapter Warning: Agno agent '{self.agent_name}' returned None content for node {node.task_id}.", "yellow"))
                 # Decide how to handle None content - raise error, return specific value, etc.
                 # For now, let it propagate, NodeProcessor might fail the task.

            return response.content # This is the core result

        except Exception as e:
            print(colored(f"  Adapter Error: Exception during Agno agent '{self.agent_name}' execution for node {node.task_id}: {e}", "red"))
            # Re-raise to allow NodeProcessor to handle it (e.g., fail the task)
            # Consider wrapping in a custom AdapterError
            raise
