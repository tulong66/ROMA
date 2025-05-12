from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskType # For TaskType enum
from .registry import register_agent_adapter, AGENT_REGISTRY, NAMED_AGENTS # Import registration function and registries
from .adapters import PlannerAdapter, ExecutorAdapter, AtomizerAdapter, AggregatorAdapter # Import adapter classes

# Import AgnoAgent definitions
from .definitions.planner_agents import simple_test_planner_agno_agent
# Import other Agno agent definitions here as you create them
# from .definitions.executor_agents import simple_writer_agno_agent, simple_search_agno_agent
# from .definitions.atomizer_agents import simple_atomizer_agno_agent
# from .definitions.aggregator_agents import simple_aggregator_agno_agent


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

# --- Placeholder for Executor Agent Registration (Example) ---
# if simple_writer_agno_agent:
#     simple_writer_adapter_instance = ExecutorAdapter(
#         agno_agent_instance=simple_writer_agno_agent,
#         agent_name="SimpleWriter"
#     )
#     register_agent_adapter(adapter=simple_writer_adapter_instance, action_verb="execute", task_type=TaskType.WRITE)
#     register_agent_adapter(adapter=simple_writer_adapter_instance, name="default_writer")


# --- Placeholder for Atomizer Agent Registration (Example) ---
# if simple_atomizer_agno_agent: # (Assuming you define this Agno agent with response_model=AtomizerOutput)
#     simple_atomizer_adapter_instance = AtomizerAdapter(
#         agno_agent_instance=simple_atomizer_agno_agent,
#         agent_name="SimpleAtomizer"
#     )
#     # Atomizers might be registered per task type
#     register_agent_adapter(adapter=simple_atomizer_adapter_instance, action_verb="atomize", task_type=TaskType.WRITE)
#     register_agent_adapter(adapter=simple_atomizer_adapter_instance, name="default_atomizer")

# --- Placeholder for Aggregator Agent Registration (Example) ---
# if simple_aggregator_agno_agent: # (Assuming this Agno agent returns a string)
#     simple_aggregator_adapter_instance = AggregatorAdapter(
#         agno_agent_instance=simple_aggregator_agno_agent,
#         agent_name="SimpleAggregator"
#     )
#     # Aggregators are usually generic for the "aggregate" action
#     register_agent_adapter(adapter=simple_aggregator_adapter_instance, action_verb="aggregate", task_type=None) # TaskType is None
#     register_agent_adapter(adapter=simple_aggregator_adapter_instance, name="default_aggregator")


print(f"AGENT_REGISTRY populated: {len(AGENT_REGISTRY)} entries.")
print(f"NAMED_AGENTS populated: {len(NAMED_AGENTS)} entries.")
if not AGENT_REGISTRY and not NAMED_AGENTS:
    print("Warning: No agent adapters were registered. The system might not find agents to process tasks.")
