from typing import List, Optional, Type, Any
from pydantic import BaseModel
from agno.agent import Agent as AgnoAgent

from sentientresearchagent.hierarchical_agent_framework.agents.base_adapter import BaseAdapter
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskType
from sentientresearchagent.hierarchical_agent_framework.agents.adapters import (
    PlannerAdapter,
    ExecutorAdapter,
    AtomizerAdapter,
    AggregatorAdapter,
    PlanModifierAdapter,
)
from sentientresearchagent.hierarchical_agent_framework.agents.definitions.planner_agents import (
    simple_test_planner_agno_agent,
    core_research_planner_agno_agent,
)
from sentientresearchagent.hierarchical_agent_framework.agents.definitions.executor_agents import (
    search_executor_agno_agent,
    search_synthesizer_agno_agent,
    basic_report_writer_agno_agent,
)
from sentientresearchagent.hierarchical_agent_framework.agents.definitions.atomizer_agents import (
    default_atomizer_agno_agent,
)
from sentientresearchagent.hierarchical_agent_framework.agents.definitions.aggregator_agents import (
    default_aggregator_agno_agent,
)
from sentientresearchagent.hierarchical_agent_framework.agents.definitions.custom_searchers import (
    OpenAICustomSearchAdapter, # For type checking if used directly in config
)

# Pydantic Models for Configuration
class RegistrationKey(BaseModel):
    action_verb: str
    task_type: Optional[TaskType] = None

class AdapterRegistrationConfig(BaseModel):
    adapter_class: Type[BaseAdapter]
    agno_agent_instance: Optional[AgnoAgent] = None
    adapter_agent_name: str
    registration_keys: List[RegistrationKey] = []
    named_registrations: List[str] = []

    model_config = {"arbitrary_types_allowed": True}

# Agent Configuration Data
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
            named_registrations=["default_planner", "SimpleTestPlanner"],
        )
    )

# CoreResearchPlanner
if core_research_planner_agno_agent:
    AGENT_CONFIGURATIONS.append(
        AdapterRegistrationConfig(
            adapter_class=PlannerAdapter,
            agno_agent_instance=core_research_planner_agno_agent,
            adapter_agent_name="CoreResearchPlanner",
            named_registrations=["CoreResearchPlanner"],
        )
    )

# SearchExecutor (LLM-based search executor)
# Now primarily registered by name, not as the default (execute, SEARCH) handler.
if search_executor_agno_agent:
    AGENT_CONFIGURATIONS.append(
        AdapterRegistrationConfig(
            adapter_class=ExecutorAdapter,
            agno_agent_instance=search_executor_agno_agent,
            adapter_agent_name="SearchExecutor",
            named_registrations=["SearchExecutor", "default_search_executor"],
        )
    )

# OpenAICustomSearchAdapter (for direct, non-LLM search)
# This will be the default handler for (execute, SEARCH)
AGENT_CONFIGURATIONS.append(
    AdapterRegistrationConfig(
        adapter_class=OpenAICustomSearchAdapter,
        agno_agent_instance=None, # OpenAICustomSearchAdapter does not use an AgnoAgent instance
        adapter_agent_name="OpenAICustomSearcher", # Name for this specific adapter instance
        registration_keys=[RegistrationKey(action_verb="execute", task_type=TaskType.SEARCH)],
        named_registrations=["OpenAICustomSearcher", "default_openai_searcher"] # Register by name as well
    )
)

# SearchSynthesizer
if search_synthesizer_agno_agent:
    AGENT_CONFIGURATIONS.append(
        AdapterRegistrationConfig(
            adapter_class=ExecutorAdapter,
            agno_agent_instance=search_synthesizer_agno_agent,
            adapter_agent_name="SearchSynthesizer",
            registration_keys=[RegistrationKey(action_verb="execute", task_type=TaskType.THINK)],
            named_registrations=["SearchSynthesizer"],
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
            named_registrations=["BasicReportWriter"],
        )
    )

# DefaultAtomizer
if default_atomizer_agno_agent:
    AGENT_CONFIGURATIONS.append(
        AdapterRegistrationConfig(
            adapter_class=AtomizerAdapter,
            agno_agent_instance=default_atomizer_agno_agent,
            adapter_agent_name="DefaultAtomizer",
            registration_keys=[RegistrationKey(action_verb="atomize", task_type=None)], # Registers for (atomize, None)
            named_registrations=["default_atomizer"],
        )
    )

# DefaultAggregator
if default_aggregator_agno_agent:
    AGENT_CONFIGURATIONS.append(
        AdapterRegistrationConfig(
            adapter_class=AggregatorAdapter,
            agno_agent_instance=default_aggregator_agno_agent,
            adapter_agent_name="DefaultAggregator",
            registration_keys=[RegistrationKey(action_verb="aggregate", task_type=None)], # Registers for (aggregate, None)
            named_registrations=["default_aggregator"],
        )
    )

# Note: Special registrations for OpenAICustomSearchAdapter and PlanModifierAdapter
# will be handled in the registry module as they don't perfectly fit this list structure.
# Alternatively, AdapterRegistrationConfig could be made more flexible
# or new config types introduced for them.
