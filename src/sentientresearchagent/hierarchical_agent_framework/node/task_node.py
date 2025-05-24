import uuid
from typing import Optional, Any, List, Dict
from pydantic import BaseModel, Field
from datetime import datetime
from loguru import logger

from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import ReplanRequestDetails
# Import from our consolidated types module
from sentientresearchagent.hierarchical_agent_framework.types import (
    TaskStatus, NodeType, TaskType, safe_task_status
)
from sentientresearchagent.exceptions import InvalidTaskStateError, TaskError
from sentientresearchagent.error_handler import safe_execute

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

    def update_status(self, new_status: TaskStatus, result: Any = None, 
                     error_msg: Optional[str] = None, result_summary: Optional[str] = None,
                     validate_transition: bool = True):
        """
        Update the task status with better error handling and validation.
        
        Args:
            new_status: New status to set (can be string or TaskStatus enum)
            result: Optional result data
            error_msg: Optional error message (will set status to FAILED if provided)
            result_summary: Optional summary of the result
            validate_transition: Whether to validate status transitions
        """
        old_status = self.status
        
        try:
            # Use safe conversion to handle string inputs
            new_status_enum = safe_task_status(new_status) if not isinstance(new_status, TaskStatus) else new_status
            
            # Validate transition if requested
            if validate_transition and not self._is_valid_transition(old_status, new_status_enum):
                # Log warning but don't fail - just warn about potentially invalid transition
                logger.warning(f"Task {self.task_id}: Potentially invalid status transition {old_status} → {new_status_enum}")
                # Don't raise exception - just log the warning and proceed
            
            self.status = new_status_enum
            self.timestamp_updated = datetime.now()
            
            if result is not None:
                self.result = result
                
            if result_summary is not None:
                self.output_summary = result_summary
                
            if error_msg is not None:
                self.error = error_msg
                self.status = TaskStatus.FAILED # Ensure status is FAILED if error is provided
            
            if self.status in [TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.NEEDS_REPLAN, TaskStatus.CANCELLED]:
                self.timestamp_completed = datetime.now()
            
            # Improved logging
            logger.info(f"Task {self.task_id} status: {old_status} → {self.status}. "
                       f"Result: {str(result)[:50] if result else 'N/A'}... "
                       f"Error: {error_msg or 'None'}")
                       
        except Exception as e:
            logger.error(f"Failed to update status for task {self.task_id}: {e}")
            # Don't re-raise here to avoid cascading failures
            # Just log the error and keep the old status
    
    def _is_valid_transition(self, from_status: TaskStatus, to_status: TaskStatus) -> bool:
        """
        Check if a status transition is valid.
        
        Args:
            from_status: Current status
            to_status: Desired new status
            
        Returns:
            True if transition is valid, False otherwise
        """
        # Define valid transitions (more flexible than before)
        valid_transitions = {
            TaskStatus.PENDING: [TaskStatus.READY, TaskStatus.RUNNING, TaskStatus.FAILED, TaskStatus.CANCELLED],
            TaskStatus.READY: [TaskStatus.RUNNING, TaskStatus.FAILED, TaskStatus.CANCELLED],
            TaskStatus.RUNNING: [TaskStatus.DONE, TaskStatus.PLAN_DONE, TaskStatus.FAILED, TaskStatus.NEEDS_REPLAN, TaskStatus.CANCELLED],
            TaskStatus.PLAN_DONE: [TaskStatus.AGGREGATING, TaskStatus.FAILED, TaskStatus.NEEDS_REPLAN],
            TaskStatus.AGGREGATING: [TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.NEEDS_REPLAN],
            TaskStatus.NEEDS_REPLAN: [TaskStatus.READY, TaskStatus.RUNNING, TaskStatus.FAILED, TaskStatus.CANCELLED],  # More flexible
            # Terminal states
            TaskStatus.DONE: [TaskStatus.NEEDS_REPLAN],  # Allow retry
            TaskStatus.FAILED: [TaskStatus.NEEDS_REPLAN, TaskStatus.READY],  # Allow retry
            TaskStatus.CANCELLED: []
        }
        
        return to_status in valid_transitions.get(from_status, [])
    
    def fail_with_error(self, error: Exception, context: Optional[Dict[str, Any]] = None):
        """
        Mark task as failed with detailed error information.
        
        Args:
            error: The exception that caused the failure
            context: Additional context information
        """
        error_message = str(error)
        if context:
            error_message += f" (Context: {context})"
            
        self.update_status(
            TaskStatus.FAILED, 
            error_msg=error_message,
            validate_transition=False  # Don't validate when handling errors
        )
        
        # Store additional error context in aux_data
        if context:
            self.aux_data.setdefault("error_context", {}).update(context)
            
        logger.error(f"Task {self.task_id} failed: {error_message}")

    def __repr__(self):
        return (f"TaskNode(id={self.task_id}, goal='{self.goal[:30]}...', "
                f"type={self.task_type}/{self.node_type}, "
                f"status={self.status}, layer={self.layer})")
