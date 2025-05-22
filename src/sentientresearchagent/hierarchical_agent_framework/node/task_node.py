import uuid
from typing import Optional, Any, List, Dict
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime
from loguru import logger

from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import ReplanRequestDetails

class TaskStatus(Enum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    PLAN_DONE = "PLAN_DONE"  # For PLAN nodes after sub-graph creation
    AGGREGATING = "AGGREGATING" # For PLAN nodes when children are done
    DONE = "DONE"
    FAILED = "FAILED"
    NEEDS_REPLAN = "NEEDS_REPLAN"
    CANCELLED = "CANCELLED"

class NodeType(Enum):
    PLAN = "PLAN"
    EXECUTE = "EXECUTE"

class TaskType(Enum):
    # General types
    WRITE = "WRITE"
    THINK = "THINK"
    SEARCH = "SEARCH"
    AGGREGATE = "AGGREGATE" # For the aggregation step itself
    # Specific types for future extension (examples)
    CODE_INTERPRET = "CODE_INTERPRET"
    IMAGE_GENERATION = "IMAGE_GENERATION"
    # ... add other specific task types as needed

class TaskNode(BaseModel):
    """Represents a single task unit in the hierarchy."""
    goal: str
    task_type: TaskType
    node_type: NodeType  # Initial type, might be changed by atomizer

    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    layer: int = 0 # Can be used as planning_depth
    parent_node_id: Optional[str] = None
    overall_objective: Optional[str] = None # The ultimate high-level goal of the entire operation

    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None # Will store Pydantic models, text, or multi-modal references
    output_summary: Optional[str] = None # Concise summary of the result for context building
    error: Optional[str] = None
    
    agent_name: Optional[str] = None # NEW: Name/type of the agent handling this task

    # For PLAN nodes, to link to the graph of their sub-tasks
    sub_graph_id: Optional[str] = None
    
    # For tracking and context building
    input_payload_dict: Optional[Dict[str, Any]] = None # What was given to the agent
    output_type_description: Optional[str] = None # e.g., "text_summary", "plan_output", "image_reference"
    timestamp_created: datetime = Field(default_factory=datetime.now)
    timestamp_updated: datetime = Field(default_factory=datetime.now)
    timestamp_completed: Optional[datetime] = None

    # For PLAN nodes to know their direct children
    # This helps in dependency management and aggregation
    planned_sub_task_ids: List[str] = Field(default_factory=list)

    # NEW: For replanning context
    replan_details: Optional[ReplanRequestDetails] = None 
    replan_reason: Optional[str] = None 
    replan_attempts: int = 0
    
    # NEW: To store arbitrary auxiliary data that might be useful for certain handlers or agents
    # For example, storing the original plan and user modification instructions during HITL replan
    aux_data: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True # Important for serialization if you pass enums around

    def update_status(self, new_status: TaskStatus, result: Any = None, error_msg: Optional[str] = None):
        self.status = new_status
        self.timestamp_updated = datetime.now()
        if result is not None:
            self.result = result
        if error_msg is not None:
            self.error = error_msg
            self.status = TaskStatus.FAILED # Ensure status is FAILED if error is provided
        
        if new_status in [TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.NEEDS_REPLAN]:
            self.timestamp_completed = datetime.now()
        
        # Basic logging, can be replaced with a proper logger
        logger.info(f"Task {self.task_id} status updated to {new_status}. Result: {str(result)[:50] if result else 'N/A'}..., Error: {error_msg}")

    def __repr__(self):
        return (f"TaskNode(id={self.task_id}, goal='{self.goal[:30]}...', "
                f"type={self.task_type}/{self.node_type}, "
                f"status={self.status}, layer={self.layer})")
