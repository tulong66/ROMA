from litellm import OpenAI
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


logger.info("Executing agents/__init__.py: Setting up and registering agents...")

# --- Instantiate and Register Planner Adapters ---
if simple_test_planner_agno_agent:
    simple_planner_adapter_instance = PlannerAdapter(
        agno_agent_instance=simple_test_planner_agno_agent,
        agent_name="SimpleTestPlanner" # This name is used for logging by the adapter
    )
    # Register for general "plan" actions for common task types
    register_agent_adapter(
        adapter=simple_planner_adapter_instance,
        action_verb="plan",
        task_type=TaskType.WRITE # <--- This will be picked for the root node
    )
    register_agent_adapter(
        adapter=simple_planner_adapter_instance,
        action_verb="plan",
        task_type=TaskType.THINK
    )
    register_agent_adapter(
        adapter=simple_planner_adapter_instance,
        action_verb="plan",
        task_type=TaskType.SEARCH
    )
    # Also register by a specific name if TaskNode.agent_name might refer to it
    register_agent_adapter(
        adapter=simple_planner_adapter_instance,
        name="default_planner" # Can be used in TaskNode(agent_name="default_planner")
    )
    register_agent_adapter(
        adapter=simple_planner_adapter_instance,
        name="SimpleTestPlanner"
    )

# --- Instantiate and Register Core Research Planner ---
if core_research_planner_agno_agent:
    core_research_planner_adapter_instance = PlannerAdapter(
        agno_agent_instance=core_research_planner_agno_agent,
        agent_name="CoreResearchPlanner" # Used for adapter logging
    )
    # Register by name, so TaskNode can specify agent_name="CoreResearchPlanner"
    register_agent_adapter(
        adapter=core_research_planner_adapter_instance,
        name="CoreResearchPlanner"
    )
    # Optionally, register for a specific action/task_type if it's a default for that
    # For example, if research planning is typically triggered by a THINK task:
    # register_agent_adapter(
    #     adapter=core_research_planner_adapter_instance,
    #     action_verb="plan",
    #     task_type=TaskType.THINK 
    # )


# --- Instantiate and Register Research Executor Agents ---

# SearchExecutor
if search_executor_agno_agent:
    search_executor_adapter_instance = ExecutorAdapter(
        agno_agent_instance=search_executor_agno_agent,
        agent_name="SearchExecutor"
    )
    register_agent_adapter(
        adapter=search_executor_adapter_instance,
        name="SearchExecutor" # For TaskNode.agent_name
    )
    # Also could be registered for (action="execute", task_type=TaskType.SEARCH) if it's a default searcher
    # register_agent_adapter(
    #     adapter=search_executor_adapter_instance,
    #     action_verb="execute",
    #     task_type=TaskType.SEARCH
    # )

# SearchSynthesizer
logger.info(f"DEBUG: Value of search_synthesizer_agno_agent before registration: {search_synthesizer_agno_agent}") # DEBUGGING STATEMENT
if search_synthesizer_agno_agent:
    search_synthesizer_adapter_instance = ExecutorAdapter(
        agno_agent_instance=search_synthesizer_agno_agent,
        agent_name="SearchSynthesizer"
    )
    register_agent_adapter(
        adapter=search_synthesizer_adapter_instance,
        name="SearchSynthesizer"
    )
    # Typically for (action="execute", task_type=TaskType.THINK)
    register_agent_adapter(
        adapter=search_synthesizer_adapter_instance,
        action_verb="execute",
        task_type=TaskType.THINK
    )

# BasicReportWriter
if basic_report_writer_agno_agent:
    basic_report_writer_adapter_instance = ExecutorAdapter(
        agno_agent_instance=basic_report_writer_agno_agent,
        agent_name="BasicReportWriter"
    )
    register_agent_adapter(
        adapter=basic_report_writer_adapter_instance,
        name="BasicReportWriter"
    )
    # Typically for (action="execute", task_type=TaskType.WRITE)
    register_agent_adapter(
        adapter=basic_report_writer_adapter_instance,
        action_verb="execute",
        task_type=TaskType.WRITE
    )


# --- Placeholder for Atomizer Agent Registration (Example) ---
# if simple_atomizer_agno_agent: # (Assuming you define this Agno agent with response_model=AtomizerOutput)
#     simple_atomizer_adapter_instance = AtomizerAdapter(
#         agno_agent_instance=simple_atomizer_agno_agent,
#         agent_name="SimpleAtomizer"
#     )
#     # Atomizers might be registered per task type
#     register_agent_adapter(adapter=simple_atomizer_adapter_instance, action_verb="atomize", task_type=TaskType.WRITE)
#     register_agent_adapter(adapter=simple_atomizer_adapter_instance, name="default_atomizer")

# --- Register the Default Atomizer Agent ---
if default_atomizer_agno_agent:
    default_atomizer_adapter_instance = AtomizerAdapter(
        agno_agent_instance=default_atomizer_agno_agent,
        agent_name="DefaultAtomizer" # For adapter logging
    )
    # Atomizers are typically general purpose for refining any task goal before planning/execution.
    # So, register for the "atomize" action verb. TaskType might not be strictly necessary
    # for selection if there's only one primary atomizer, or it can be registered for all common task types.
    # For simplicity, let's register it by name and for a general "atomize" action.
    # The NodeProcessor will specifically request an "atomize" action.
    register_agent_adapter(
        adapter=default_atomizer_adapter_instance,
        action_verb="atomize",
        task_type=None # Indicates it can atomize any task type goal
    )
    register_agent_adapter(
        adapter=default_atomizer_adapter_instance,
        name="default_atomizer" # Allow calling by name
    )
    logger.info(f"Registered adapter: {default_atomizer_adapter_instance.agent_name} for atomization")
else:
    logger.warning("DefaultAtomizer_Agno agent not available. Atomization step will be skipped or limited.")


# --- Register the Default Aggregator Agent ---
logger.info(f"DEBUG: Value of default_aggregator_agno_agent before registration: {default_aggregator_agno_agent}") # DEBUGGING STATEMENT
if default_aggregator_agno_agent:
    default_aggregator_adapter_instance = AggregatorAdapter( # Use AggregatorAdapter
        agno_agent_instance=default_aggregator_agno_agent,
        agent_name="DefaultAggregator" # For adapter logging
    )
    # Register for the generic "aggregate" action, typically TaskType is None or not specified
    # as aggregation is a phase rather than a specific task type from planning.
    # The get_agent_adapter logic might need to handle finding an aggregator
    # when a node is in AGGREGATING status.
    # For now, let's register it by name and for a general aggregate action.
    register_agent_adapter(
        adapter=default_aggregator_adapter_instance,
        action_verb="aggregate", 
        task_type=None # Indicates it's a general aggregator for any task type parent
    )
    register_agent_adapter(
        adapter=default_aggregator_adapter_instance,
        name="default_aggregator" # Allow calling by name
    )
    logger.info(f"Registered adapter: {default_aggregator_adapter_instance.agent_name} for aggregation")


# Register OpenAICustomSearchAdapter directly
# Ensure OpenAI is available and client can be initialized
try:
    if OpenAI: # Check if OpenAI was successfully imported in custom_searchers
        openai_direct_search_adapter_instance = OpenAICustomSearchAdapter() # Uses default "gpt-4.1"
        register_agent_adapter(
            adapter=openai_direct_search_adapter_instance,
            name="OpenAICustomSearcher" # The name to use when assigning tasks
        )
        # Also register it for the generic ('execute', TaskType.SEARCH) key
        register_agent_adapter(
            adapter=openai_direct_search_adapter_instance,
            action_verb="execute",
            task_type=TaskType.SEARCH
        )
        logger.info(f"Registered direct adapter: {openai_direct_search_adapter_instance.adapter_name} as 'OpenAICustomSearcher' AND for ('execute', SEARCH)")
    else:
        logger.warning("Warning: OpenAI library not available, OpenAICustomSearchAdapter not registered.")
except Exception as e:
    logger.warning(f"Warning: Could not initialize and register OpenAICustomSearchAdapter: {e}")


# Register the Plan Modifier Agno Agent instance by its name (for potential direct use if needed, not typical for adapters)
if plan_modifier_agno_agent:
    if PLAN_MODIFIER_AGENT_NAME in NAMED_AGENTS: # PLAN_MODIFIER_AGENT_NAME is "PlanModifier_Agno"
        logger.warning(f"Agno agent instance {PLAN_MODIFIER_AGENT_NAME} already exists in NAMED_AGENTS. Overwriting.")
    NAMED_AGENTS[PLAN_MODIFIER_AGENT_NAME] = plan_modifier_agno_agent # Storing the AgnoAgent itself
    logger.info(f"Stored Agno agent instance '{PLAN_MODIFIER_AGENT_NAME}' in NAMED_AGENTS.")
else:
    logger.error(f"Plan Modifier Agno agent ({PLAN_MODIFIER_AGENT_NAME}) was not initialized. Not adding to NAMED_AGENTS.")

# Register the Plan Modifier Adapter instance using its specific key for lookup by NodeProcessor
PLAN_MODIFIER_ADAPTER_KEY = "PlanModifier" 
try:
    if not plan_modifier_agno_agent:
        logger.error(f"Cannot instantiate PlanModifierAdapter: plan_modifier_agno_agent ('{PLAN_MODIFIER_AGENT_NAME}') is not available.")
        raise ValueError(f"Agno agent '{PLAN_MODIFIER_AGENT_NAME}' is required for PlanModifierAdapter but was not loaded.")

    plan_modifier_adapter_instance = PlanModifierAdapter(
        agno_agent_instance=plan_modifier_agno_agent,
        # Set the adapter's internal agent_name. Using the KEY ensures clarity if logs from the adapter use self.agent_name.
        agent_name=PLAN_MODIFIER_ADAPTER_KEY 
    )
    
    # Register the adapter instance by its specific key directly into NAMED_AGENTS
    # This allows NodeProcessor to fetch it using NAMED_AGENTS.get("PlanModifier")
    register_agent_adapter(
        adapter=plan_modifier_adapter_instance,
        name=PLAN_MODIFIER_ADAPTER_KEY  # This will put it in NAMED_AGENTS with the key "PlanModifier"
    )
    # The logger message from register_agent_adapter will be something like:
    # "AgentRegistry: Registered adapter 'PlanModifierAdapter' with name 'PlanModifier'"
    # (Actual class name of adapter is PlanModifierAdapter, its self.agent_name is set to "PlanModifier")

except Exception as e:
    logger.error(f"Failed to initialize or register PlanModifierAdapter: {e}")
    import traceback
    logger.error(traceback.format_exc())


logger.info(f"AGENT_REGISTRY populated: {len(AGENT_REGISTRY)} entries.")
logger.info(f"NAMED_AGENTS populated: {len(NAMED_AGENTS)} entries.")
if not AGENT_REGISTRY and not NAMED_AGENTS:
    logger.warning("Warning: No agent adapters were registered. The system might not find agents to process tasks.")
