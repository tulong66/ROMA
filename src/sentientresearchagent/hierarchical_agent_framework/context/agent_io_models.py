from pydantic import BaseModel, Field
from typing import List, Any, Optional, Dict

# --- Plan Output Schemas (used by Planner Agents and NodeProcessor) ---
class SubTask(BaseModel):
    """Schema for a single sub-task planned by a Planner agent."""
    goal: str = Field(..., description="Precise description of the sub-task goal.")
    # Assuming TaskType and NodeType enums will be defined in a shared types module or node.task_node
    # For now, using strings and will be validated/converted by adapter or node_processor
    task_type: str = Field(..., description="Type of task (e.g., 'WRITE', 'THINK', 'SEARCH').")
    node_type: str = Field(..., description="Node type ('EXECUTE' for atomic, 'PLAN' for complex).")
    agent_name: Optional[str] = Field(None, description="Suggested agent for this sub-task.")
    # You could add estimated_effort, dependencies_within_plan etc. later

class PlanOutput(BaseModel):
    """Output schema for a Planner agent, detailing the sub-tasks."""
    sub_tasks: List[SubTask] = Field(..., description="List of planned sub-tasks.")
    # Could add overall_plan_summary or other metadata from the planner

# --- Atomizer Output Schema ---
class AtomizerOutput(BaseModel):
    """Output schema for Atomizer agents."""
    is_atomic: bool = Field(..., description="True if the refined goal is atomic, False if complex and needs planning.")
    updated_goal: str = Field(..., description="The refined task goal after considering context.")
    # Optionally, the atomizer could also suggest a task_type or agent_name if it changes fundamentally
    # suggested_task_type: Optional[str] = None
    # suggested_agent_name: Optional[str] = None


# --- Context Structure for Agents ---
class ContextItem(BaseModel):
    """A single piece of structured context provided to an agent."""
    source_task_id: str
    source_task_goal: str # Goal of the task that produced this context
    content: Any # The actual data (text, Pydantic model, multi-modal reference)
    content_type_description: str # e.g., 'outline', 'search_result_summary', 'plan_output'
    # Optional fields for more advanced context handling:
    # relevance_score: Optional[float] = None
    # timestamp_created: Optional[datetime] = None # When the context item was generated
    # modality: Optional[str] = None # For future multi-modal: 'text', 'image', 'audio'

class AgentTaskInput(BaseModel):
    """Structured input provided to an agent for processing a task."""
    current_task_id: str
    current_goal: str
    current_task_type: str # String representation of TaskNode.TaskType
    
    overall_project_goal: Optional[str] = None
    relevant_context_items: List[ContextItem] = Field(default_factory=list)
    
    # Configuration or agent-specific parameters can also be passed here
    # agent_config: Optional[Dict[str, Any]] = None

# --- Research Agent I/O Schemas ---
class WebSearchResultsOutput(BaseModel):
    """Output schema for a SearchExecutor agent, detailing the search results."""
    query_used: str = Field(..., description="The exact search query that was executed.")
    # DuckDuckGoTools search_ddg method returns a list of dictionaries like:
    # [{'title': '...', 'href': '...', 'body': '...'}]
    # We'll map 'href' to 'link' and 'body' to 'snippet' for consistency if needed,
    # or adjust this model to expect 'href' and 'body'.
    # For now, let's assume the agent can format it to 'title', 'link', 'snippet'.
    results: List[Dict[str, str]] = Field(..., description="A list of search results, each ideally with 'title', 'link', and 'snippet'.")