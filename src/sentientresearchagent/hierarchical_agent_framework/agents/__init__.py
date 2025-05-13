from litellm import OpenAI
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskType # For TaskType enum
from .registry import register_agent_adapter, AGENT_REGISTRY, NAMED_AGENTS # Import registration function and registries
from .adapters import PlannerAdapter, ExecutorAdapter, AtomizerAdapter, AggregatorAdapter # Import adapter classes

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
from .definitions.aggregator_agents import default_aggregator_agno_agent # Import the new aggregator

# Removed import from .definitions.research_agents as its contents are moved

# Import the new adapter
from .definitions.custom_searchers import OpenAICustomSearchAdapter


print("Executing agents/__init__.py: Setting up and registering agents...")

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
        task_type=TaskType.WRITE # Example: this planner handles planning for WRITE tasks
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
    # register_agent_adapter(
    #     adapter=search_synthesizer_adapter_instance,
    #     action_verb="execute",
    #     task_type=TaskType.THINK
    # )

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
    # register_agent_adapter(
    #     adapter=basic_report_writer_adapter_instance,
    #     action_verb="execute",
    #     task_type=TaskType.WRITE
    # )


# --- Placeholder for Atomizer Agent Registration (Example) ---
# if simple_atomizer_agno_agent: # (Assuming you define this Agno agent with response_model=AtomizerOutput)
#     simple_atomizer_adapter_instance = AtomizerAdapter(
#         agno_agent_instance=simple_atomizer_agno_agent,
#         agent_name="SimpleAtomizer"
#     )
#     # Atomizers might be registered per task type
#     register_agent_adapter(adapter=simple_atomizer_adapter_instance, action_verb="atomize", task_type=TaskType.WRITE)
#     register_agent_adapter(adapter=simple_atomizer_adapter_instance, name="default_atomizer")

# --- Register the Default Aggregator Agent ---
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
    print(f"Registered adapter: {default_aggregator_adapter_instance.agent_name} for aggregation")


# Register OpenAICustomSearchAdapter directly
# Ensure OpenAI is available and client can be initialized
try:
    if OpenAI: # Check if OpenAI was successfully imported in custom_searchers
        openai_direct_search_adapter_instance = OpenAICustomSearchAdapter() # Uses default "gpt-4.1"
        register_agent_adapter(
            adapter=openai_direct_search_adapter_instance,
            name="OpenAICustomSearcher" # The name to use when assigning tasks
        )
        print(f"Registered direct adapter: {openai_direct_search_adapter_instance.adapter_name} as 'OpenAICustomSearcher'")
    else:
        print("Warning: OpenAI library not available, OpenAICustomSearchAdapter not registered.")
except Exception as e:
    print(f"Warning: Could not initialize and register OpenAICustomSearchAdapter: {e}")


print(f"AGENT_REGISTRY populated: {len(AGENT_REGISTRY)} entries.")
print(f"NAMED_AGENTS populated: {len(NAMED_AGENTS)} entries.")
if not AGENT_REGISTRY and not NAMED_AGENTS:
    print("Warning: No agent adapters were registered. The system might not find agents to process tasks.")
