from typing import Dict, Optional, List
from pydantic import BaseModel
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskType


class AgentBlueprint(BaseModel):
    name: str
    description: str
    planner_adapter_name: str
    executor_adapter_names: Dict[TaskType, str]
    atomizer_adapter_name: Optional[str] = "DefaultAtomizer"
    aggregator_adapter_name: Optional[str] = "DefaultAggregator"
    plan_modifier_adapter_name: Optional[str] = "PlanModifier"

    default_node_agent_name_prefix: Optional[str] = None


DEFAULT_DEEP_RESEARCH_BLUEPRINT = AgentBlueprint(
    name="DeepResearchAgent",
    description="A comprehensive research agent for in-depth analysis and report generation.",
    planner_adapter_name="CoreResearchPlanner",
    executor_adapter_names={
        TaskType.SEARCH: "OpenAICustomSearcher",
        TaskType.THINK: "SearchSynthesizer",
        TaskType.WRITE: "BasicReportWriter",
    },
    atomizer_adapter_name="DefaultAtomizer",
    aggregator_adapter_name="DefaultAggregator",
    plan_modifier_adapter_name="PlanModifier",
    default_node_agent_name_prefix="DeepResearch"
)

AVAILABLE_AGENT_BLUEPRINTS: List[AgentBlueprint] = [
    DEFAULT_DEEP_RESEARCH_BLUEPRINT,
]

def get_blueprint_by_name(name: str) -> Optional[AgentBlueprint]:
    for bp in AVAILABLE_AGENT_BLUEPRINTS:
        if bp.name == name:
            return bp
    return None
