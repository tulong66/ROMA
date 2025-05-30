from typing import Dict, Tuple, Optional, Any
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskType
from sentientresearchagent.hierarchical_agent_framework.agents.base_adapter import BaseAdapter
from loguru import logger

# AGENT_REGISTRY: Maps (action_verb, TaskType enum) to an adapter instance
AGENT_REGISTRY: Dict[Tuple[str, Optional[TaskType]], BaseAdapter] = {}

# NAMED_AGENTS: Maps a string name to an adapter instance
NAMED_AGENTS: Dict[str, Any] = {}


def register_agent_adapter(adapter: BaseAdapter,
                           action_verb: Optional[str] = None,
                           task_type: Optional[TaskType] = None,
                           name: Optional[str] = None):
    """
    Register an adapter instance in the agent registry.
    
    Args:
        adapter: The adapter instance to register
        action_verb: Action verb for action-based registration
        task_type: Task type for action-based registration
        name: Name for named registration
    """
    if not isinstance(adapter, BaseAdapter):
        logger.error(f"Registration failed: Expected BaseAdapter, got {type(adapter)}. Adapter: {adapter}")
        return

    registered = False
    adapter_type_name = type(adapter).__name__
    adapter_name_attr = getattr(adapter, 'agent_name', adapter_type_name)

    if action_verb:
        key = (action_verb.lower(), task_type)
        if key in AGENT_REGISTRY and AGENT_REGISTRY[key] != adapter:
            logger.warning(f"Overwriting agent '{type(AGENT_REGISTRY[key]).__name__}' with '{adapter_name_attr}' in AGENT_REGISTRY for key {key}")
        AGENT_REGISTRY[key] = adapter
        logger.info(f"AgentRegistry: Registered adapter '{adapter_name_attr}' for action '{action_verb}', task_type '{task_type.name if task_type else None}'")
        registered = True
    
    if name:
        if name in NAMED_AGENTS and NAMED_AGENTS[name] != adapter:
            logger.warning(f"Overwriting agent '{str(NAMED_AGENTS[name])}' with '{adapter_name_attr}' in NAMED_AGENTS for name '{name}'")
        NAMED_AGENTS[name] = adapter
        logger.info(f"AgentRegistry: Registered adapter '{adapter_name_attr}' with name '{name}'")
        registered = True
    
    if not registered:
        logger.warning(f"Adapter '{adapter_name_attr}' was not registered. Provide action/task_type or a name.")


def get_agent_adapter(node: TaskNode, action_verb: str) -> Optional[BaseAdapter]:
    """
    Retrieve an appropriate adapter for a given TaskNode and action verb.
    
    Args:
        node: The TaskNode requiring an adapter
        action_verb: The action to be performed
        
    Returns:
        BaseAdapter instance or None if no suitable adapter found
    """
    # DEBUG: Print current registry state
    logger.info(f"🔍 AgentRegistry DEBUG: Current AGENT_REGISTRY keys: {list(AGENT_REGISTRY.keys())}")
    logger.info(f"🔍 AgentRegistry DEBUG: Looking for node {node.task_id} with task_type={node.task_type} (type: {type(node.task_type)}), action_verb='{action_verb}'")
    
    node_agent_name = getattr(node, 'agent_name', None)
    
    # 1. Try by specific agent_name assigned to the node
    if node_agent_name:
        retrieved_agent = NAMED_AGENTS.get(node_agent_name)
        if isinstance(retrieved_agent, BaseAdapter):
            adapter = retrieved_agent
            logger.info(f"AgentRegistry: Found adapter '{type(adapter).__name__}' by name '{node_agent_name}' for node {node.task_id}.")
            return adapter
        elif retrieved_agent is not None:
             logger.warning(f"AgentRegistry: Found item named '{node_agent_name}' in NAMED_AGENTS, but it's not a BaseAdapter (type: {type(retrieved_agent)}). Cannot use for node {node.task_id}. Falling back.")
        else:
            logger.info(f"AgentRegistry: Agent name '{node_agent_name}' for node {node.task_id} not found in NAMED_AGENTS. Falling back.")

    # 2. Fallback to (action_verb, task_type) lookup
    # Handle both enum and string task_types for robustness
    if isinstance(node.task_type, TaskType):
        key_task_type = node.task_type
    elif isinstance(node.task_type, str):
        try:
            key_task_type = TaskType[node.task_type.upper()]
            logger.info(f"🔍 AgentRegistry: Converted string task_type '{node.task_type}' to enum {key_task_type} for node {node.task_id}")
        except KeyError:
            logger.warning(f"AgentRegistry: Invalid task_type string '{node.task_type}' for node {node.task_id}. Cannot lookup adapter.")
            return None
    else:
        key_task_type = None
    
    # Special handling for "aggregate" and "atomize" which often use (verb, None) as key
    if action_verb.lower() in ["aggregate", "atomize"]:
        key_task_type = None
    
    key = (action_verb.lower(), key_task_type)
    logger.info(f"🔍 AgentRegistry DEBUG: Looking up key: {key}")
    
    adapter = AGENT_REGISTRY.get(key)
    if adapter:
        logger.info(f"AgentRegistry: Found adapter '{type(adapter).__name__}' for action '{action_verb}', task_type '{key_task_type}' for node {node.task_id}.")
        return adapter
    else:
        logger.warning(f"AgentRegistry: No adapter found for action '{action_verb}', task_type '{key_task_type}' for node {node.task_id}.")
        # DEBUG: Show what keys are available
        logger.info(f"🔍 AgentRegistry DEBUG: Available keys: {list(AGENT_REGISTRY.keys())}")
        return None