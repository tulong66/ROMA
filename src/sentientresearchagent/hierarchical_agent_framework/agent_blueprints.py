from typing import Dict, Optional, List
from pydantic import BaseModel
from loguru import logger

# Import TaskType from the centralized types module
from .types import TaskType

# REMOVED: These imports create a circular dependency with profile_loader.py
# from .agent_configs.profile_loader import load_profile, list_profiles


class AgentBlueprint(BaseModel):
    """Enhanced agent blueprint supporting task-specific planners and root-specific planning."""
    name: str
    description: str
    
    # Enhanced planner mapping - different planners for different task types
    planner_adapter_names: Dict[TaskType, str] = {}  # TaskType -> planner_name
    
    # NEW: Root-specific planner (overrides task-specific planners for root node)
    root_planner_adapter_name: Optional[str] = None
    
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


# Updated research blueprint with root-specific planner
DEFAULT_DEEP_RESEARCH_BLUEPRINT = AgentBlueprint(
    name="DeepResearchAgent",
    description="A comprehensive research agent with specialized root planner and task-specific sub-planners.",
    
    # Root-specific planner for initial task decomposition
    root_planner_adapter_name="DeepResearchPlanner",
    
    # Task-specific planners for sub-tasks
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

DEFAULT_GENERAL_AGENT_BLUEPRINT = AgentBlueprint(
    name="GeneralAgent",
    description="A general agent for solving complex tasks",
    # Root-specific planner for initial task decomposition
    root_planner_adapter_name="GeneralTaskSolver",
    
    # Task-specific planners for sub-tasks
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
    default_node_agent_name_prefix="GeneralTaskSolver"
)

AVAILABLE_AGENT_BLUEPRINTS: List[AgentBlueprint] = [
    DEFAULT_DEEP_RESEARCH_BLUEPRINT,
    DEFAULT_GENERAL_AGENT_BLUEPRINT,
]

def get_blueprint_by_name(profile_name: str) -> Optional[AgentBlueprint]:
    """
    Loads an agent blueprint by its profile name.
    
    DEPRECATED: This function's presence here creates a circular dependency.
    Use ProfileLoader().load_profile(profile_name) from a higher-level module instead.
    """
    logger.warning("get_blueprint_by_name is deprecated here due to circular imports. Use ProfileLoader directly.")
    # To prevent a hard crash, we do a local import, but this is not ideal.
    from .agent_configs.profile_loader import load_profile
    return load_profile(profile_name)


def get_available_blueprints() -> Dict[str, AgentBlueprint]:
    """
    Loads all available blueprints from profiles.
    
    DEPRECATED: This function's presence here creates a circular dependency.
    Use ProfileLoader().load_all_profiles() from a higher-level module instead.
    """
    logger.warning("get_available_blueprints is deprecated here due to circular imports. Use ProfileLoader directly.")
    # To prevent a hard crash, we do a local import, but this is not ideal.
    from .agent_configs.profile_loader import ProfileLoader
    loader = ProfileLoader()
    return loader.load_all_profiles()
