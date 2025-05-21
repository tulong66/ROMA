import re
from typing import List, Optional, Any, Dict
from loguru import logger
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import AgentTaskInput, ContextItem # Removed Planner specific models
from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import KnowledgeStore, TaskRecord # Adjusted import
# Removed TaskStatus import as it's not directly used here anymore
# Assuming TaskNode related enums/types are not directly needed here, TaskRecord uses Literals

# Removed summarization utility import, it's now in planner_context_builder
# from ..agents.utils import get_context_summary, TARGET_WORD_COUNT_FOR_CTX_SUMMARIES

# NEW IMPORT for context strategies
from .strategies import (
    ContextResolutionStrategy,
    ParentContextStrategy,
    PrerequisiteSiblingContextStrategy,
    AncestorBranchContextStrategy,
    GoalReferenceContextStrategy,
)

# Removed get_task_record_path_to_root as it's used by planner context builder now
# from .context_utils import get_task_record_path_to_root 

# --- Default and Task-Specific Strategy Configurations ---

DEFAULT_CONTEXT_STRATEGIES: List[ContextResolutionStrategy] = [
    ParentContextStrategy(),
    PrerequisiteSiblingContextStrategy(),
    AncestorBranchContextStrategy(), 
    GoalReferenceContextStrategy(),
]

# TASK_TYPE_STRATEGY_MAPPING defines which strategies to use for specific task types.
# The key is the task_type string (e.g., "WRITE", "PLAN", "RESEARCH_WEB").
# The value is a list of instantiated ContextResolutionStrategy objects.
# If a task type is not found here, DEFAULT_CONTEXT_STRATEGIES will be used.
TASK_TYPE_STRATEGY_MAPPING: Dict[str, List[ContextResolutionStrategy]] = {
    # "DEFAULT" key isn't strictly necessary if we always fallback to DEFAULT_CONTEXT_STRATEGIES object
    "WRITE": [
        ParentContextStrategy(),
        PrerequisiteSiblingContextStrategy(),
        AncestorBranchContextStrategy(), # Crucial for writers
        GoalReferenceContextStrategy(),
    ],
    "THINK": [ # Similar to WRITE, might need broad context
        ParentContextStrategy(),
        PrerequisiteSiblingContextStrategy(),
        AncestorBranchContextStrategy(),
        GoalReferenceContextStrategy(),
    ],
    "PLAN": [ # Planners might need more focused context
        ParentContextStrategy(),
        PrerequisiteSiblingContextStrategy(), # See what came before in this plan
        GoalReferenceContextStrategy(), # Check if goal refers to other tasks
        # AncestorBranchContextStrategy might be too broad for initial planning,
        # but could be useful for re-planning or very deep plans.
    ],
    "RESEARCH_WEB": [ # Example: A web research task might prioritize different things
        ParentContextStrategy(), # What is the parent task asking for?
        GoalReferenceContextStrategy(), # Any specific prior results to build upon?
        # PrerequisiteSiblingContextStrategy might be less relevant if it's a standalone search
    ]
    # Add other task types and their specific strategy lists as needed.
    # For example, an "AGGREGATE" task might have no strategies here if its context
    # is entirely prepared by NodeProcessor.
}


def resolve_context_for_agent(
    current_task_id: str,
    current_goal: str,
    current_task_type: str, 
    agent_name: str,
    knowledge_store: KnowledgeStore,
    overall_project_goal: Optional[str] = None,
) -> AgentTaskInput:
    logger.info(f"ContextBuilder: Resolving context for task '{current_task_id}' (Agent: {agent_name}, Type: {current_task_type})")
    
    relevant_items: List[ContextItem] = []
    processed_context_source_ids = set()

    current_task_record = knowledge_store.get_record(current_task_id)
    if not current_task_record:
        logger.warning(f"ContextBuilder Warning: TaskRecord for current task {current_task_id} not found. Returning empty context.")
        return AgentTaskInput(
            current_task_id=current_task_id, 
            current_goal=current_goal,
            current_task_type=current_task_type or "UNKNOWN", # Ensure task type is a string
            overall_project_goal=overall_project_goal, 
            relevant_context_items=[]
        )

    # Get the list of strategies based on the current task type.
    # Fallback to DEFAULT_CONTEXT_STRATEGIES if the specific type is not in the mapping.
    context_strategies = TASK_TYPE_STRATEGY_MAPPING.get(str(current_task_type), DEFAULT_CONTEXT_STRATEGIES) # Ensure current_task_type is string for dict key
    
    if str(current_task_type) not in TASK_TYPE_STRATEGY_MAPPING:
        logger.debug(f"Task type '{current_task_type}' not found in TASK_TYPE_STRATEGY_MAPPING. Using default strategies.")
    
    logger.debug(f"Using context strategies for task type '{current_task_type}': {[s.__class__.__name__ for s in context_strategies]}")

    for strategy in context_strategies:
        try:
            # Ensure current_task_type is passed as a string to strategies if they expect it
            strategy_items = strategy.get_context(
                current_task_record=current_task_record,
                knowledge_store=knowledge_store,
                processed_context_source_ids=processed_context_source_ids,
                overall_project_goal=overall_project_goal,
                current_task_type=str(current_task_type) 
            )
            relevant_items.extend(strategy_items)
        except Exception as e:
            logger.error(f"ContextBuilder: Error executing strategy {strategy.__class__.__name__} for task {current_task_id}: {e}", exc_info=True)
    
    if relevant_items:
        logger.success(f"ContextBuilder: Found {len(relevant_items)} relevant context items for task '{current_task_id}'.")
    else:
        logger.warning(f"ContextBuilder: No relevant context items found for task '{current_task_id}'.")
        
    return AgentTaskInput(
        current_task_id=current_task_id,
        current_goal=current_goal,
        current_task_type=str(current_task_type), # Ensure task type is a string
        overall_project_goal=overall_project_goal,
        relevant_context_items=relevant_items
    )

# --- Planner-specific input building functions have been moved to planner_context_builder.py ---
