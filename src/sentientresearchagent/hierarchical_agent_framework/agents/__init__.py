from typing import List, Optional, Type, Any
from pydantic import BaseModel

from litellm import OpenAI # type: ignore
from agno.agent import Agent as AgnoAgent # Corrected import

from sentientresearchagent.hierarchical_agent_framework.agents.base_adapter import BaseAdapter
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskType # For TaskType enum
from .registry import register_agent_adapter, AGENT_REGISTRY, NAMED_AGENTS # Import registration function and registries
from .adapters import PlannerAdapter, ExecutorAdapter, AtomizerAdapter, AggregatorAdapter, PlanModifierAdapter # Import adapter classes
from loguru import logger
# Import AgnoAgent definitions
from .definitions.planner_agents import simple_test_planner_agno_agent, core_research_planner_agno_agent
from .definitions.executor_agents import (
    simple_writer_agno_agent, # Assuming this might still be used or defined
    simple_search_agno_agent, # Assuming this might still be used or defined
    search_executor_agno_agent,
    search_synthesizer_agno_agent,
    basic_report_writer_agno_agent,
    # openai_custom_search_agno_agent # This will be replaced
)
# from .definitions.atomizer_agents import simple_atomizer_agno_agent
from .definitions.atomizer_agents import default_atomizer_agno_agent # Import the new default atomizer
from .definitions.aggregator_agents import default_aggregator_agno_agent # Import the new aggregator

# Removed import from .definitions.research_agents as its contents are moved

# Import the new adapter
from .definitions.custom_searchers import OpenAICustomSearchAdapter

# Import the new agent and adapter
from .definitions.plan_modifier_agents import plan_modifier_agno_agent, PLAN_MODIFIER_AGENT_NAME


logger.info("Executing agents/__init__.py: Setting up agent configurations...")

# --- Pydantic Models for Configuration ---
class RegistrationKey(BaseModel):
    action_verb: str
    task_type: Optional[TaskType] = None

class AdapterRegistrationConfig(BaseModel):
    adapter_class: Type[BaseAdapter]
    agno_agent_instance: Optional[AgnoAgent] = None # Optional for adapters like OpenAICustomSearchAdapter
    adapter_agent_name: str # Name passed to the adapter's constructor
    registration_keys: List[RegistrationKey] = []
    named_registrations: List[str] = [] # For registration by specific names

    model_config = {"arbitrary_types_allowed": True}

# --- Agent Configuration Data ---

AGENT_CONFIGURATIONS: List[AdapterRegistrationConfig] = []

# SimpleTestPlanner
if simple_test_planner_agno_agent:
    AGENT_CONFIGURATIONS.append(
        AdapterRegistrationConfig(
            adapter_class=PlannerAdapter,
            agno_agent_instance=simple_test_planner_agno_agent,
            adapter_agent_name="SimpleTestPlanner",
            registration_keys=[
                RegistrationKey(action_verb="plan", task_type=TaskType.WRITE),
                RegistrationKey(action_verb="plan", task_type=TaskType.THINK),
                RegistrationKey(action_verb="plan", task_type=TaskType.SEARCH),
            ],
            named_registrations=["default_planner", "SimpleTestPlanner"]
        )
    )

# CoreResearchPlanner
if core_research_planner_agno_agent:
    AGENT_CONFIGURATIONS.append(
        AdapterRegistrationConfig(
            adapter_class=PlannerAdapter,
            agno_agent_instance=core_research_planner_agno_agent,
            adapter_agent_name="CoreResearchPlanner",
            named_registrations=["CoreResearchPlanner"]
            # Example for action_verb/task_type registration if desired:
            # registration_keys=[RegistrationKey(action_verb="plan", task_type=TaskType.THINK)]
        )
    )

# SearchExecutor
if search_executor_agno_agent:
    AGENT_CONFIGURATIONS.append(
        AdapterRegistrationConfig(
            adapter_class=ExecutorAdapter,
            agno_agent_instance=search_executor_agno_agent,
            adapter_agent_name="SearchExecutor",
            named_registrations=["SearchExecutor"]
            # Example for action_verb/task_type registration if desired:
            # registration_keys=[RegistrationKey(action_verb="execute", task_type=TaskType.SEARCH)]
        )
    )

# SearchSynthesizer
logger.info(f"DEBUG: Value of search_synthesizer_agno_agent before registration: {search_synthesizer_agno_agent}") # DEBUGGING STATEMENT
if search_synthesizer_agno_agent:
    AGENT_CONFIGURATIONS.append(
        AdapterRegistrationConfig(
            adapter_class=ExecutorAdapter,
            agno_agent_instance=search_synthesizer_agno_agent,
            adapter_agent_name="SearchSynthesizer",
            registration_keys=[RegistrationKey(action_verb="execute", task_type=TaskType.THINK)],
            named_registrations=["SearchSynthesizer"]
        )
    )

# BasicReportWriter
if basic_report_writer_agno_agent:
    AGENT_CONFIGURATIONS.append(
        AdapterRegistrationConfig(
            adapter_class=ExecutorAdapter,
            agno_agent_instance=basic_report_writer_agno_agent,
            adapter_agent_name="BasicReportWriter",
            registration_keys=[RegistrationKey(action_verb="execute", task_type=TaskType.WRITE)],
            named_registrations=["BasicReportWriter"]
        )
    )

# DefaultAtomizer
if default_atomizer_agno_agent:
    AGENT_CONFIGURATIONS.append(
        AdapterRegistrationConfig(
            adapter_class=AtomizerAdapter,
            agno_agent_instance=default_atomizer_agno_agent,
            adapter_agent_name="DefaultAtomizer",
            registration_keys=[RegistrationKey(action_verb="atomize", task_type=None)],
            named_registrations=["default_atomizer"]
        )
    )
else:
    logger.warning("DefaultAtomizer_Agno agent not available. Atomization step will be skipped or limited.")

# DefaultAggregator
logger.info(f"DEBUG: Value of default_aggregator_agno_agent before registration: {default_aggregator_agno_agent}") # DEBUGGING STATEMENT
if default_aggregator_agno_agent:
    AGENT_CONFIGURATIONS.append(
        AdapterRegistrationConfig(
            adapter_class=AggregatorAdapter,
            agno_agent_instance=default_aggregator_agno_agent,
            adapter_agent_name="DefaultAggregator",
            registration_keys=[RegistrationKey(action_verb="aggregate", task_type=None)],
            named_registrations=["default_aggregator"]
        )
    )
else:
    logger.warning("DefaultAggregator_Agno agent not available. Aggregation step will be skipped or limited.")


# --- Processing Configurations and Registering Adapters ---
for config in AGENT_CONFIGURATIONS:
    try:
        if config.agno_agent_instance:
            adapter_instance = config.adapter_class(
                agno_agent_instance=config.agno_agent_instance,
                agent_name=config.adapter_agent_name
            )
        elif config.adapter_class == OpenAICustomSearchAdapter: # Special case for direct adapter instantiation
             adapter_instance = OpenAICustomSearchAdapter() # Assumes OpenAICustomSearchAdapter has agent_name or similar internally
             # If OpenAICustomSearchAdapter needs adapter_agent_name, adjust its constructor or this logic
        else:
            logger.error(f"Cannot instantiate adapter for {config.adapter_agent_name}: No AgnoAgent instance and not a known special case.")
            continue

        for key_reg in config.registration_keys:
            register_agent_adapter(
                adapter=adapter_instance,
                action_verb=key_reg.action_verb,
                task_type=key_reg.task_type
            )
        for name_reg in config.named_registrations:
            register_agent_adapter(
                adapter=adapter_instance,
                name=name_reg
            )
        logger.info(f"Successfully configured and registered adapter: {config.adapter_agent_name}")

    except Exception as e:
        logger.error(f"Failed to configure or register adapter {config.adapter_agent_name}: {e}")
        import traceback
        logger.error(traceback.format_exc())


# --- Handle Special Registrations (Not fitting the common AdapterRegistrationConfig pattern cleanly) ---

# OpenAICustomSearchAdapter (direct instantiation and registration)
# This is a non-LLM adapter, instantiated directly.
try:
    # Assuming OpenAI is available (litellm should handle this)
    # We check if OpenAI class itself is available which custom_searchers.py might depend on.
    if "OpenAI" in globals() and OpenAI is not None : # Check if litellm.OpenAI was imported
        openai_direct_search_adapter_instance = OpenAICustomSearchAdapter() # Uses default "gpt-4.1" or its own config

        register_agent_adapter(
            adapter=openai_direct_search_adapter_instance,
            name="OpenAICustomSearcher"
        )
        register_agent_adapter(
            adapter=openai_direct_search_adapter_instance,
            action_verb="execute",
            task_type=TaskType.SEARCH
        )
        # The adapter_name for logging comes from OpenAICustomSearchAdapter.adapter_name
        logger.info(f"Registered direct adapter: {getattr(openai_direct_search_adapter_instance, 'adapter_name', 'OpenAICustomSearchAdapter')} as 'OpenAICustomSearcher' AND for ('execute', SEARCH)")
    else:
        logger.warning("Warning: OpenAI library (from litellm) not available or not imported as OpenAI, OpenAICustomSearchAdapter not registered.")
except Exception as e:
    logger.warning(f"Warning: Could not initialize and register OpenAICustomSearchAdapter: {e}")
    import traceback
    logger.error(traceback.format_exc())


# PlanModifier AgnoAgent instance (stored directly in NAMED_AGENTS)
if plan_modifier_agno_agent:
    if PLAN_MODIFIER_AGENT_NAME in NAMED_AGENTS:
        logger.warning(f"Agno agent instance {PLAN_MODIFIER_AGENT_NAME} already exists in NAMED_AGENTS. Overwriting.")
    NAMED_AGENTS[PLAN_MODIFIER_AGENT_NAME] = plan_modifier_agno_agent
    logger.info(f"Stored Agno agent instance '{PLAN_MODIFIER_AGENT_NAME}' in NAMED_AGENTS.")
else:
    logger.error(f"Plan Modifier Agno agent ({PLAN_MODIFIER_AGENT_NAME}) was not initialized. Not adding to NAMED_AGENTS.")

# PlanModifierAdapter (registered by specific name)
PLAN_MODIFIER_ADAPTER_KEY = "PlanModifier"
try:
    if not plan_modifier_agno_agent:
        logger.error(f"Cannot instantiate PlanModifierAdapter: plan_modifier_agno_agent ('{PLAN_MODIFIER_AGENT_NAME}') is not available.")
        # Not raising error here to allow rest of the system to potentially load
    else:
        plan_modifier_adapter_instance = PlanModifierAdapter(
            agno_agent_instance=plan_modifier_agno_agent,
            agent_name=PLAN_MODIFIER_ADAPTER_KEY
        )
        register_agent_adapter(
            adapter=plan_modifier_adapter_instance,
            name=PLAN_MODIFIER_ADAPTER_KEY
        )
        # Logger message will be handled by register_agent_adapter
except Exception as e:
    logger.error(f"Failed to initialize or register PlanModifierAdapter: {e}")
    import traceback
    logger.error(traceback.format_exc())


logger.info(f"AGENT_REGISTRY populated: {len(AGENT_REGISTRY)} entries.")
logger.info(f"NAMED_AGENTS populated: {len(NAMED_AGENTS)} entries.")
if not AGENT_REGISTRY and not NAMED_AGENTS:
    logger.warning("Warning: No agent adapters were registered. The system might not find agents to process tasks.")
