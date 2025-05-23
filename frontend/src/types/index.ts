export interface TaskNode {
  task_id: string
  goal: string
  task_type: string
  node_type: 'PLAN' | 'EXECUTE'
  agent_name?: string
  layer: number
  parent_node_id?: string
  sub_graph_id?: string
  status: TaskStatus
  output_summary?: string
  full_result?: any
  error?: string
  input_payload_summary?: string
  timestamp_created?: string
  timestamp_updated?: string
  timestamp_completed?: string
  planned_sub_task_ids?: string[]
  input_context_sources?: ContextSource[]
}

export type TaskStatus = 
  | 'PENDING'
  | 'READY' 
  | 'RUNNING'
  | 'PLAN_DONE'
  | 'AGGREGATING'
  | 'DONE'
  | 'FAILED'
  | 'NEEDS_REPLAN'
  | 'CANCELLED'

export interface ContextSource {
  source_task_id: string
  source_task_goal_summary: string
  content_type: string
  content_type_description?: string
}

export interface TaskGraph {
  edges: GraphEdge[]
}

export interface GraphEdge {
  source: string
  target: string
}

export interface APIResponse {
  overall_project_goal?: string
  all_nodes: Record<string, TaskNode>
  graphs: Record<string, TaskGraph>
}

export interface HITLRequest {
  checkpoint_name: string
  context_message: string
  data_for_review: any
  node_id: string
  current_attempt: number
}

export interface HITLResponse {
  user_choice: 'approved' | 'request_modification' | 'aborted'
  message?: string
  modification_instructions?: string
}

// React Flow types
export interface FlowNode {
  id: string
  type: string
  position: { x: number; y: number }
  data: {
    label: string
    node: TaskNode
    isSelected?: boolean
  }
  style?: any
}

export interface FlowEdge {
  id: string
  source: string
  target: string
  type?: string
  style?: any
  data?: any
} 