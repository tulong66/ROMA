from pydantic import BaseModel

class NodeProcessorConfig(BaseModel):
    enable_hitl_after_plan_generation: bool = True 
    enable_hitl_after_atomizer: bool = False
    enable_hitl_before_execute: bool = False
    enable_hitl_after_modified_plan: bool = True
    max_planning_layer: int = 2
    max_replan_attempts: int = 5
    
    # NEW: Flag to indicate root plan only mode
    hitl_root_plan_only: bool = False