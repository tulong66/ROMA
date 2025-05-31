from typing import Dict, Optional, List
from pydantic import BaseModel
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskType


class AgentBlueprint(BaseModel):
    """Enhanced agent blueprint supporting task-specific planners and extensible action verbs."""
    name: str
    description: str
    
    # Enhanced planner mapping - different planners for different task types
    planner_adapter_names: Dict[TaskType, str] = {}  # TaskType -> planner_name
    
    # Keep existing executor mapping
    executor_adapter_names: Dict[TaskType, str] = {}  # TaskType -> executor_name
    
    # Keep existing single agents for other actions
    atomizer_adapter_name: Optional[str] = "DefaultAtomizer"
    aggregator_adapter_name: Optional[str] = "DefaultAggregator"
    plan_modifier_adapter_name: Optional[str] = "PlanModifier"
    
    # Fallbacks for backward compatibility and robustness
    default_planner_adapter_name: Optional[str] = "default_planner"
    default_executor_adapter_name: Optional[str] = "default_executor"
    default_node_agent_name_prefix: Optional[str] = None
    
    # LEGACY: Keep old single planner field for backward compatibility
    planner_adapter_name: Optional[str] = None


# Updated research blueprint using new structure
DEFAULT_DEEP_RESEARCH_BLUEPRINT = AgentBlueprint(
    name="DeepResearchAgent",
    description="A comprehensive research agent with task-specific planners and executors.",
    
    # Task-specific planners
    planner_adapter_names={
        TaskType.SEARCH: "CoreResearchPlanner",      # Specialized for search planning
        TaskType.WRITE: "CoreResearchPlanner",       # Could be different if needed
        TaskType.THINK: "CoreResearchPlanner",       # Could be different if needed
    },
    
    # Task-specific executors
    executor_adapter_names={
        TaskType.SEARCH: "OpenAICustomSearcher",
        TaskType.THINK: "SearchSynthesizer",
        TaskType.WRITE: "BasicReportWriter",
    },
    
    # Single agents for other actions
    atomizer_adapter_name="DefaultAtomizer",
    aggregator_adapter_name="DefaultAggregator",
    plan_modifier_adapter_name="PlanModifier",
    
    # Fallbacks
    default_planner_adapter_name="CoreResearchPlanner",
    default_executor_adapter_name="SearchSynthesizer",
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
