from typing import Dict, Tuple, Optional, Any
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskType # For enums
from sentientresearchagent.hierarchical_agent_framework.agents.base_adapter import BaseAdapter # The new base adapter

# Placeholder for actual AgnoAgent instances and Adapter instances.
# These will be defined and instantiated in other files (e.g., definitions/ , adapters.py)
# For now, let's assume they will be populated.

# Example:
# from .definitions.planner_agents import adk_planner_agno_agent # An AgnoAgent instance
# from .adapters import PlannerAdapter # A BaseAdapter implementation
# planner_adapter_instance = PlannerAdapter(adk_planner_agno_agent)


# AGENT_REGISTRY: Maps (action_verb, TaskType enum) to an adapter instance
AGENT_REGISTRY: Dict[Tuple[str, Optional[TaskType]], BaseAdapter] = {}

# NAMED_AGENTS: Maps a string name (e.g., from TaskNode.agent_name) to an adapter instance
NAMED_AGENTS: Dict[str, BaseAdapter] = {}


def register_agent_adapter(adapter: BaseAdapter, 
                           action_verb: Optional[str] = None, 
                           task_type: Optional[TaskType] = None, 
                           name: Optional[str] = None):
    """
    Helper function to register an adapter instance.
    An adapter can be registered by an action/task_type key, a name, or both.
    """
    if not isinstance(adapter, BaseAdapter):
        raise ValueError("Can only register instances of BaseAdapter or its subclasses.")

    registered = False
    if action_verb: # Check only for action_verb presence for key-based registration
        key = (action_verb.lower(), task_type) # task_type can correctly be None here
        if key in AGENT_REGISTRY:
            print(f"Warning: Overwriting agent in AGENT_REGISTRY for key {key}")
        AGENT_REGISTRY[key] = adapter
        print(f"AgentRegistry: Registered adapter '{type(adapter).__name__}' for action '{action_verb}', task_type '{task_type.name if task_type else None}'")
        registered = True
    
    if name:
        if name in NAMED_AGENTS:
            print(f"Warning: Overwriting agent in NAMED_AGENTS for name '{name}'")
        NAMED_AGENTS[name] = adapter
        print(f"AgentRegistry: Registered adapter '{type(adapter).__name__}' with name '{name}'")
        registered = True
    
    if not registered:
        print(f"Warning: Adapter '{type(adapter).__name__}' was not registered. Provide action/task_type or a name.")


def get_agent_adapter(node: TaskNode, action_verb: str) -> Optional[BaseAdapter]:
    """
    Retrieves an agent adapter based on the node's assigned agent_name (if any)
    or by the action_verb and node.task_type.
    """
    # ---- START DIAGNOSTIC & TEMPORARY FIX ----
    if isinstance(node.task_type, str):
        # This block should ideally not be hit if TaskNode instances are always correctly typed.
        print(f"AgentRegistry DEBUG: node.task_type for {node.task_id} ('{node.goal[:30]}...') was a string: '{node.task_type}'. Attempting conversion to enum.")
        original_str_task_type = node.task_type
        try:
            # Pydantic models are mutable by default, so direct assignment should work.
            # This modifies the task_type attribute of the node instance.
            node.task_type = TaskType[original_str_task_type.upper()]
            print(f"AgentRegistry DEBUG: Successfully converted node.task_type for {node.task_id} to enum: {node.task_type}")
        except KeyError:
            print(f"AgentRegistry ERROR: Failed to convert string task_type '{original_str_task_type}' to TaskType enum for node {node.task_id}. Lookup will likely use the original string and fail if the registry expects an enum.")
            # If conversion fails, node.task_type remains the problematic string.
            # The subsequent lookup AGENT_REGISTRY.get(key) will use this string.
    elif not isinstance(node.task_type, TaskType) and node.task_type is not None:
        # Log if it's neither string nor TaskType enum (and not None, which is valid for 'aggregate' key_task_type)
        print(f"AgentRegistry WARNING: node.task_type for {node.task_id} is unexpected type: {type(node.task_type)} (value: {node.task_type}). Expected TaskType enum or str.")
    # ---- END DIAGNOSTIC & TEMPORARY FIX ----

    adapter: Optional[BaseAdapter] = None

    # 1. Try by specific agent_name assigned to the node
    if hasattr(node, 'agent_name') and node.agent_name:
        adapter = NAMED_AGENTS.get(node.agent_name)
        if adapter:
            print(f"AgentRegistry: Found adapter '{type(adapter).__name__}' by name '{node.agent_name}' for node {node.task_id}.")
            return adapter
        else:
            print(f"AgentRegistry: Agent name '{node.agent_name}' for node {node.task_id} not found in NAMED_AGENTS. Falling back.")

    # 2. Fallback to (action_verb, task_type) lookup
    # Adjust key for aggregation where task_type might be less relevant for adapter choice
    # After the block above, node.task_type should be an enum if it was a convertible string.
    key_task_type = None if action_verb.lower() == "aggregate" else node.task_type
    key = (action_verb.lower(), key_task_type)
    
    adapter = AGENT_REGISTRY.get(key)
    if adapter:
        print(f"AgentRegistry: Found adapter '{type(adapter).__name__}' by key {key} for node {node.task_id}.")
    else:
        # This log will now show the key with an enum if conversion worked, or still with string if not.
        print(f"AgentRegistry: No adapter found for node {node.task_id} with key {key}.")
        # You might want to try a more generic fallback, e.g., (action_verb, None) if task_type specific one fails
        # Or raise an error if no suitable agent can be found.
        # For example:
        # generic_key = (action_verb.lower(), None)
        # adapter = AGENT_REGISTRY.get(generic_key)
        # if adapter:
        #     print(f"AgentRegistry: Found generic adapter '{type(adapter).__name__}' by key {generic_key} for node {node.task_id}.")

    return adapter
