from typing import Dict, Tuple, Optional, Any, List, Type
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskType # For enums
from sentientresearchagent.hierarchical_agent_framework.agents.base_adapter import BaseAdapter # The new base adapter
from loguru import logger

# Import Pydantic models and configurations from the new configurations module
# configurations.py should be in the same directory (agents/)
from .configurations import AdapterRegistrationConfig 

# Import specific adapter classes and AgnoAgent instances for "special" registrations
from .adapters import PlanModifierAdapter
from .definitions.custom_searchers import OpenAICustomSearchAdapter # For direct instantiation if needed
from .definitions.plan_modifier_agents import plan_modifier_agno_agent, PLAN_MODIFIER_AGENT_NAME

# Try to import OpenAI from litellm for checking its availability, but don't fail if not present
try:
    from litellm import OpenAI
except ImportError:
    OpenAI = None # type: ignore
    logger.info("litellm.OpenAI not available. OpenAICustomSearchAdapter might have limited functionality if it depends on it being globally available.")


# AGENT_REGISTRY: Maps (action_verb, TaskType enum) to an adapter instance
AGENT_REGISTRY: Dict[Tuple[str, Optional[TaskType]], BaseAdapter] = {}

# NAMED_AGENTS: Maps a string name (e.g., from TaskNode.agent_name) to an adapter instance
# This can store BaseAdapter instances or AgnoAgent instances directly if needed for some lookup patterns
NAMED_AGENTS: Dict[str, Any] = {} # Changed to Any to accommodate AgnoAgent instances directly


def register_agent_adapter(adapter: BaseAdapter,
                           action_verb: Optional[str] = None,
                           task_type: Optional[TaskType] = None,
                           name: Optional[str] = None):
    """
    Helper function to register an adapter instance.
    An adapter can be registered by an action/task_type key, a name, or both.
    """
    if not isinstance(adapter, BaseAdapter):
        logger.error(f"Registration failed: Expected BaseAdapter, got {type(adapter)}. Adapter: {adapter}")
        # raise ValueError("Can only register instances of BaseAdapter or its subclasses.") # Made it a log error instead of raising
        return


    registered = False
    adapter_type_name = type(adapter).__name__
    adapter_name_attr = getattr(adapter, 'agent_name', adapter_type_name) # Use agent_name if adapter has it

    if action_verb: # Check only for action_verb presence for key-based registration
        key = (action_verb.lower(), task_type) # task_type can correctly be None here
        if key in AGENT_REGISTRY and AGENT_REGISTRY[key] != adapter: # Check if different instance
            logger.warning(f"Overwriting agent '{type(AGENT_REGISTRY[key]).__name__}' with '{adapter_name_attr}' in AGENT_REGISTRY for key {key}")
        AGENT_REGISTRY[key] = adapter
        logger.info(f"AgentRegistry: Registered adapter '{adapter_name_attr}' for action '{action_verb}', task_type '{task_type.name if task_type else None}'")
        registered = True
    
    if name:
        if name in NAMED_AGENTS and NAMED_AGENTS[name] != adapter: # Check if different instance
            logger.warning(f"Overwriting agent '{str(NAMED_AGENTS[name])}' with '{adapter_name_attr}' in NAMED_AGENTS for name '{name}'")
        NAMED_AGENTS[name] = adapter
        logger.info(f"AgentRegistry: Registered adapter '{adapter_name_attr}' with name '{name}'")
        registered = True
    
    if not registered:
        logger.warning(f"Adapter '{adapter_name_attr}' was not registered. Provide action/task_type or a name.")


def initialize_adapters_from_configurations(configs: List[AdapterRegistrationConfig]):
    """
    Processes a list of AdapterRegistrationConfig, instantiates adapters,
    and registers them.
    """
    logger.info(f"Initializing adapters from {len(configs)} configurations...")
    for config in configs:
        try:
            adapter_instance: Optional[BaseAdapter] = None
            
            if config.adapter_class == OpenAICustomSearchAdapter:
                # MODIFIED LINE: Call OpenAICustomSearchAdapter without agent_name,
                # as its __init__ does not accept it.
                adapter_instance = config.adapter_class() 
                
                # The adapter_agent_name from config (e.g., "OpenAICustomSearcher")
                # will be used for registration purposes (in NAMED_AGENTS and logs),
                # even if the instance's internal 'agent_name' is different (e.g., "OpenAICustomSearchAdapter").
                logger.info(f"Instantiated adapter for config name '{config.adapter_agent_name}' (class: {config.adapter_class.__name__}). "
                            f"Instance's internal agent_name: {getattr(adapter_instance, 'agent_name', 'N/A')}")
            elif config.agno_agent_instance:
                adapter_instance = config.adapter_class(
                    agno_agent_instance=config.agno_agent_instance,
                    agent_name=config.adapter_agent_name
                )
                agno_name = getattr(config.agno_agent_instance, 'name', 'Unnamed AgnoAgent')
                logger.info(f"Instantiated adapter {config.adapter_agent_name} with Agno agent {agno_name}")
            else:
                logger.error(f"Cannot instantiate adapter for {config.adapter_agent_name}: "
                             f"No AgnoAgent instance provided and not a recognized special type like OpenAICustomSearchAdapter "
                             f"that can be instantiated without one.")
                continue

            if adapter_instance is None:
                logger.error(f"Adapter instance for {config.adapter_agent_name} was None after instantiation attempt. Skipping registration.")
                continue

            # Register by (action_verb, task_type) keys
            for key_reg in config.registration_keys:
                register_agent_adapter(
                    adapter=adapter_instance,
                    action_verb=key_reg.action_verb,
                    task_type=key_reg.task_type
                )
            
            # Register by specific names
            for name_reg in config.named_registrations:
                register_agent_adapter(
                    adapter=adapter_instance,
                    name=name_reg
                )
            
            # Ensure the primary adapter_agent_name from the config is also registered as a named agent,
            # if not already covered by named_registrations.
            # This makes the adapter lookupable by its primary configured name.
            if config.adapter_agent_name not in config.named_registrations:
                if config.adapter_agent_name not in NAMED_AGENTS:
                    register_agent_adapter(adapter=adapter_instance, name=config.adapter_agent_name)
                elif NAMED_AGENTS[config.adapter_agent_name] != adapter_instance:
                    logger.warning(
                        f"Named agent {config.adapter_agent_name} from config was already registered "
                        f"with a different instance ({type(NAMED_AGENTS[config.adapter_agent_name]).__name__} vs {type(adapter_instance).__name__}). "
                        f"Check configurations to avoid conflicts."
                    )

            logger.info(f"Successfully processed configuration for adapter: {config.adapter_agent_name}")

        except Exception as e:
            logger.error(f"Failed to process configuration or register adapter {config.adapter_agent_name}: {e}", exc_info=True)


def register_special_cases():
    """
    Handles registration of agents/adapters that don't fit neatly into the
    AdapterRegistrationConfig list or require direct manipulation of NAMED_AGENTS.
    """
    logger.info("Registering special case adapters and Agno agents...")

    # 1. PlanModifier AgnoAgent instance (stored directly in NAMED_AGENTS for potential direct use)
    if plan_modifier_agno_agent:
        current_in_registry = NAMED_AGENTS.get(PLAN_MODIFIER_AGENT_NAME)
        if current_in_registry and current_in_registry != plan_modifier_agno_agent:
            logger.warning(
                f"Agno agent instance {PLAN_MODIFIER_AGENT_NAME} already exists in NAMED_AGENTS "
                f"and is different ({type(current_in_registry).__name__}). Overwriting with direct Agno agent "
                f"({type(plan_modifier_agno_agent).__name__})."
            )
            NAMED_AGENTS[PLAN_MODIFIER_AGENT_NAME] = plan_modifier_agno_agent
            logger.info(f"Overwrote Agno agent instance '{PLAN_MODIFIER_AGENT_NAME}' in NAMED_AGENTS.")
        elif not current_in_registry:
            NAMED_AGENTS[PLAN_MODIFIER_AGENT_NAME] = plan_modifier_agno_agent
            logger.info(f"Stored Agno agent instance '{PLAN_MODIFIER_AGENT_NAME}' in NAMED_AGENTS.")
        else: # It's the same instance, already there
            logger.info(f"Agno agent instance '{PLAN_MODIFIER_AGENT_NAME}' already correctly stored in NAMED_AGENTS.")
            
    else:
        logger.error(f"Plan Modifier Agno agent ({PLAN_MODIFIER_AGENT_NAME}) was not initialized. Cannot store in NAMED_AGENTS.")

    # 2. PlanModifierAdapter (registered by specific name, uses the AgnoAgent above)
    # Ensure this adapter is registered if its Agno agent is available and it's not already registered.
    # It's expected that AGENT_CONFIGURATIONS would ideally handle this.
    PLAN_MODIFIER_ADAPTER_REG_NAME = "PlanModifier" 
    if plan_modifier_agno_agent:
        if NAMED_AGENTS.get(PLAN_MODIFIER_ADAPTER_REG_NAME) is None or \
           not isinstance(NAMED_AGENTS.get(PLAN_MODIFIER_ADAPTER_REG_NAME), PlanModifierAdapter):
            try:
                logger.info(f"Attempting to register PlanModifierAdapter as '{PLAN_MODIFIER_ADAPTER_REG_NAME}' in special_cases "
                            f"(either not found or not correct type in NAMED_AGENTS).")
                plan_modifier_adapter_instance = PlanModifierAdapter(
                    agno_agent_instance=plan_modifier_agno_agent,
                    agent_name=PLAN_MODIFIER_ADAPTER_REG_NAME 
                )
                register_agent_adapter(
                    adapter=plan_modifier_adapter_instance,
                    name=PLAN_MODIFIER_ADAPTER_REG_NAME
                )
            except Exception as e:
                logger.error(f"Failed to initialize or register PlanModifierAdapter ('{PLAN_MODIFIER_ADAPTER_REG_NAME}') in special cases: {e}", exc_info=True)
        else:
            logger.info(f"PlanModifierAdapter already registered as '{PLAN_MODIFIER_ADAPTER_REG_NAME}'. Skipping re-registration in special_cases.")
    else:
        logger.warning(f"Cannot instantiate PlanModifierAdapter ('{PLAN_MODIFIER_ADAPTER_REG_NAME}') in special_cases: "
                       f"plan_modifier_agno_agent ('{PLAN_MODIFIER_AGENT_NAME}') is not available.")
    
    # OpenAICustomSearchAdapter is now configured via AGENT_CONFIGURATIONS.
    logger.info("Finished processing special cases in agent registration.")


def get_agent_adapter(node: TaskNode, action_verb: str) -> Optional[BaseAdapter]:
    """
    Retrieves an agent adapter based on the node's assigned agent_name (if any)
    or by the action_verb and node.task_type.
    """
    # ---- START DIAGNOSTIC & TEMPORARY FIX ----
    # This section attempts to handle cases where node.task_type might be a string
    # instead of the expected TaskType enum. Ideally, TaskNode instances should
    # always have correctly typed attributes.
    current_task_type = node.task_type
    if isinstance(current_task_type, str):
        logger.debug(f"AgentRegistry: node.task_type for {node.task_id} ('{node.goal[:30]}...') was a string: '{current_task_type}'. Attempting conversion to enum.")
        try:
            # This assumes Pydantic model fields are mutable or being handled in a context where this change is safe.
            node.task_type = TaskType[current_task_type.upper()] 
            logger.debug(f"AgentRegistry: Successfully converted node.task_type for {node.task_id} to enum: {node.task_type}")
        except KeyError:
            logger.error(f"AgentRegistry: Failed to convert string task_type '{current_task_type}' to TaskType enum for node {node.task_id}. Lookup will use original string.")
            # If conversion fails, node.task_type remains the original string.
            # The lookup key will use this string. If the registry was populated with enums, this will likely fail.
    elif not isinstance(current_task_type, TaskType) and current_task_type is not None:
        logger.warning(f"AgentRegistry: node.task_type for {node.task_id} is unexpected type: {type(current_task_type)} (value: {current_task_type}). Expected TaskType enum, str, or None.")
    # ---- END DIAGNOSTIC & TEMPORARY FIX ----

    adapter: Optional[BaseAdapter] = None
    node_agent_name = getattr(node, 'agent_name', None)

    # 1. Try by specific agent_name assigned to the node
    if node_agent_name:
        retrieved_agent = NAMED_AGENTS.get(node_agent_name)
        if isinstance(retrieved_agent, BaseAdapter):
            adapter = retrieved_agent
            logger.info(f"AgentRegistry: Found adapter '{type(adapter).__name__}' by name '{node_agent_name}' for node {node.task_id}.")
            return adapter
        elif retrieved_agent is not None: # It was in NAMED_AGENTS but not a BaseAdapter
             logger.warning(f"AgentRegistry: Found item named '{node_agent_name}' in NAMED_AGENTS, but it's not a BaseAdapter (type: {type(retrieved_agent)}). Cannot use for node {node.task_id}. Falling back.")
        else:
            logger.info(f"AgentRegistry: Agent name '{node_agent_name}' for node {node.task_id} not found in NAMED_AGENTS. Falling back.")

    # 2. Fallback to (action_verb, task_type) lookup
    # Use the (potentially converted) node.task_type for the key.
    key_task_type = node.task_type if isinstance(node.task_type, TaskType) else None # Default to None if not a TaskType (e.g. if string conversion failed)
    
    # Special handling for "aggregate" and "atomize" which often use (verb, None) as key
    if action_verb.lower() in ["aggregate", "atomize"]:
        key_task_type = None
        
    key = (action_verb.lower(), key_task_type)
    
    adapter = AGENT_REGISTRY.get(key)
    if adapter:
        logger.info(f"AgentRegistry: Found adapter '{type(adapter).__name__}' by key {key} for node {node.task_id}.")
    else:
        logger.info(f"AgentRegistry: No adapter found for node {node.task_id} with key {key}.")
        # Fallback to (action_verb, None) if task_type specific one fails and key_task_type was not already None
        if key_task_type is not None: 
            generic_key = (action_verb.lower(), None)
            adapter = AGENT_REGISTRY.get(generic_key)
            if adapter:
                logger.info(f"AgentRegistry: Found generic adapter '{type(adapter).__name__}' by fallback key {generic_key} for node {node.task_id}.")
            else:
                logger.info(f"AgentRegistry: No adapter found for node {node.task_id} with fallback key {generic_key} either.")
    
    if not adapter:
        logger.error(f"AgentRegistry: CRITICAL - No suitable adapter found for node {node.task_id} (Goal: '{node.goal[:50]}...', Action: '{action_verb}', Original TaskType: '{current_task_type}')")
        # Optionally, could raise an error here: raise ValueError("No suitable agent adapter found")

    return adapter