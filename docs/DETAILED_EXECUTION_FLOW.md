# SentientResearchAgent: Detailed Execution Flow Documentation

## Table of Contents
1. [Overview](#overview)
2. [Initial Query Submission](#initial-query-submission)
3. [System Initialization](#system-initialization)
4. [Node Processing Pipeline](#node-processing-pipeline)
5. [LLM Call Sequences](#llm-call-sequences)
6. [State Transitions](#state-transitions)
7. [Human-in-the-Loop (HITL) Integration](#human-in-the-loop-hitl-integration)
8. [Final Aggregation](#final-aggregation)
9. [Complete Flow Example](#complete-flow-example)

## Overview

SentientResearchAgent is a hierarchical AI agent framework that decomposes complex research tasks into manageable subtasks, processes them through specialized agents, and aggregates results. The system uses a graph-based execution model with nodes representing tasks at different levels of abstraction.

### Key Components
- **TaskNode**: Basic unit of work with status, results, and relationships
- **TaskGraph**: Manages node relationships and execution dependencies
- **ExecutionEngine**: Orchestrates the execution flow
- **NodeProcessor**: Handles individual node state transitions
- **AgentRegistry**: Manages specialized agents for different task types
- **KnowledgeStore**: Persists and retrieves task results and context

## Initial Query Submission

### 1. Entry Points

There are multiple ways to submit a query:

#### A. Programmatic API
```python
# Using ProfiledSentientAgent
agent = ProfiledSentientAgent.create_with_profile("deep_research_agent")
result = await agent.arun(goal="Research quantum computing applications")
```

#### B. Web API (via Flask server)
```
POST /api/projects/{project_id}/execute
{
    "goal": "Research quantum computing applications",
    "profile": "deep_research_agent"
}
```

#### C. WebSocket Real-time
```javascript
socket.emit('execute_task', {
    project_id: 'xxx',
    goal: 'Research quantum computing applications'
})
```

### 2. Initial Task Creation

When a query is submitted:

1. **Root Node Creation**:
   ```python
   root_node = TaskNode(
       task_id="root",
       goal=user_goal,
       node_type=NodeType.ROOT,
       status=TaskStatus.READY,
       task_type=TaskType.PLAN  # Root typically starts as PLAN
   )
   ```

2. **Task Graph Initialization**:
   ```python
   task_graph = TaskGraph()
   task_graph.add_node(root_node)
   task_graph.root_node_id = root_node.task_id
   ```

3. **Knowledge Store Setup**:
   - Creates initial record for root node
   - Establishes context storage

## System Initialization

### 1. SystemManager Setup

The SystemManager orchestrates all components:

```python
system_manager = SystemManager(config_path="sentient.yaml")
```

This initializes:
- Configuration loading
- Component registry
- Profile management
- Execution environment

### 2. ExecutionEngine Creation

```python
execution_engine = ExecutionEngine(
    task_graph=task_graph,
    knowledge_store=knowledge_store,
    agent_registry=agent_registry,
    node_processor=node_processor,
    config=config
)
```

### 3. Agent Profile Loading

Profiles define agent hierarchies and specializations:
- Loads from `agent_configs/profiles/{profile_name}.yaml`
- Creates AgentBlueprint with node type mappings
- Configures agent selection strategy

## Node Processing Pipeline

### Phase 1: READY → PLANNING

When a node enters READY status:

1. **Handler Selection**:
   - `ReadyNodeHandler` is invoked
   - Determines if node needs planning or direct execution

2. **Planning Decision**:
   ```python
   if node.node_type == NodeType.LEAF:
       # Direct execution
       transition_to_executing()
   else:
       # Needs planning
       transition_to_planning()
   ```

3. **LLM Call #1 - Planning Agent**:
   - **Agent**: Selected based on task_type (e.g., `DeepResearchPlanner_Agno`)
   - **Context Building**:
     ```python
     context = resolve_input_for_planner_agent(
         node=node,
         knowledge_store=knowledge_store,
         task_graph=task_graph
     )
     ```
   - **Context includes**:
     - Parent task plan (if exists)
     - Sibling task results
     - Overall project goal
     - Task-specific instructions

   - **Prompt Structure**:
     ```
     Project Goal: {overall_goal}
     Current Task: {node.goal}
     Parent Context: {parent_plan}
     Completed Siblings: {sibling_results}
     
     Create a detailed plan...
     ```

   - **Expected Output**: `PlanOutput` with subtasks

### Phase 2: PLANNING → PLAN_MODIFICATION (Optional)

If HITL is enabled for plan review:

1. **HITL Intervention Point**:
   - Plan sent to frontend via WebSocket
   - User can approve/modify/reject

2. **LLM Call #2 - Plan Modifier** (if modified):
   - **Agent**: `PlanModifier_Agno`
   - **Input**: Original plan + user modifications
   - **Output**: Updated `PlanOutput`

### Phase 3: PLAN_MODIFICATION → ATOMIZATION

1. **Atomization Check**:
   - Determines if subtasks need further breakdown
   - Checks complexity thresholds

2. **LLM Call #3 - Atomizer Agent** (if needed):
   - **Agent**: `TaskAtomizer_Agno`
   - **Purpose**: Break down complex subtasks
   - **Context**: Parent plan + task details
   - **Output**: `AtomizerOutput` with atomic tasks

### Phase 4: ATOMIZATION → PLAN_DONE

1. **Sub-node Creation**:
   ```python
   for i, subtask in enumerate(plan.sub_tasks):
       sub_node = TaskNode(
           task_id=f"{parent.task_id}.{i}",
           goal=subtask.task,
           parent_task_id=parent.task_id,
           node_type=determine_node_type(subtask),
           task_type=subtask.task_type
       )
       task_graph.add_node(sub_node)
   ```

2. **Dependency Resolution**:
   - Maps `depends_on_indices` to actual node IDs
   - Creates edges in task graph

3. **Status Updates**:
   - Parent: `PLAN_DONE`
   - Sub-nodes with no dependencies: `READY`
   - Sub-nodes with dependencies: `PENDING`

### Phase 5: EXECUTING

For leaf nodes or direct execution:

1. **LLM Call #4 - Execution Agent**:
   - **Agent**: Specialized by task_type
     - `WebSearcher_Agno` for SEARCH tasks
     - `DataAnalyzer_Agno` for ANALYZE tasks
     - `InformationSynthesizer_Agno` for SYNTHESIZE tasks
     - etc.
   
   - **Context Building**:
     ```python
     context = resolve_context_for_agent(
         node=node,
         agent_instance=selected_agent,
         knowledge_store=knowledge_store,
         task_graph=task_graph
     )
     ```

   - **Execution**:
     ```python
     result = await agent.arun(
         goal=node.goal,
         context=context_items,
         task_type=node.task_type
     )
     ```

2. **Result Storage**:
   - Updates node with execution result
   - Stores in knowledge store
   - Triggers dependent node checks

### Phase 6: DONE → AGGREGATING

When all sub-nodes complete:

1. **Parent Notification**:
   - ExecutionEngine detects all children done
   - Transitions parent to AGGREGATING

2. **LLM Call #5 - Aggregation**:
   - **Agent**: `InformationSynthesizer_Agno` or similar
   - **Context**: All sub-node results
   - **Purpose**: Combine and synthesize findings
   
   ```python
   aggregation_context = [
       ContextItem(
           source_task_id=child.task_id,
           content=child.result,
           content_type="subtask_result"
       )
       for child in completed_children
   ]
   ```

## LLM Call Sequences

### Complete LLM Call Chain for a Complex Task

1. **Root Planning** (Call #1)
   - Agent: `DeepResearchPlanner_Agno`
   - Creates high-level plan

2. **Sub-node Planning** (Calls #2-N)
   - Each non-leaf node gets planning call
   - Parallel planning when possible

3. **Atomization** (Optional)
   - For complex subtasks
   - Further decomposition

4. **Execution** (Calls #N+1-M)
   - Leaf nodes execute specialized tasks
   - Parallel execution based on dependencies

5. **Aggregation** (Calls #M+1-P)
   - Bottom-up aggregation
   - Each parent aggregates children

### Context Flow

Context builds hierarchically:

```
Root Context: [Project Goal]
    ↓
Level 1 Context: [Project Goal, Root Plan]
    ↓
Level 2 Context: [Project Goal, Root Plan, Parent Plan, Sibling Results]
    ↓
Execution Context: [All above + Relevant Knowledge Store entries]
```

## State Transitions

### Node Status Flow

```
PENDING → READY → PLANNING → PLAN_MODIFICATION → ATOMIZATION → PLAN_DONE
                     ↓                                              ↓
                 EXECUTING ←────────────────────────────────────────┘
                     ↓
                   DONE → (triggers parent) → AGGREGATING → DONE
                     ↓
                  FAILED/CANCELLED
```

### Transition Rules

1. **PENDING → READY**: All dependencies completed
2. **READY → PLANNING**: Non-leaf nodes
3. **READY → EXECUTING**: Leaf nodes
4. **PLANNING → PLAN_MODIFICATION**: HITL intervention
5. **PLAN_DONE → (creates children)**: Sub-node generation
6. **EXECUTING → DONE**: Successful execution
7. **All children DONE → parent AGGREGATING**: Automatic

## Human-in-the-Loop (HITL) Integration

### HITL Checkpoints

1. **Plan Generation Review**:
   ```python
   if config.enable_hitl and config.hitl_plan_generation:
       response = await hitl_coordinator.request_plan_review(
           node=node,
           plan=generated_plan
       )
   ```

2. **Plan Modification**:
   - User edits via web interface
   - WebSocket real-time communication

3. **Execution Review** (optional):
   - Before executing critical tasks
   - Confirmation dialogs

### HITL Flow

```
Generate Plan → Send to Frontend → User Review → 
    ↓ Approve: Continue
    ↓ Modify: Call Plan Modifier → Continue
    ↓ Reject: Fail node
```

## Final Aggregation

### Bottom-Up Aggregation

1. **Leaf Completion**:
   - Execution results stored
   - Parent notified

2. **Parent Aggregation Trigger**:
   ```python
   if all(child.status == TaskStatus.DONE for child in children):
       parent.update_status(TaskStatus.AGGREGATING)
   ```

3. **Aggregation Process**:
   - Collect all child results
   - Build aggregation context
   - Call synthesis agent
   - Store aggregated result

4. **Recursive Aggregation**:
   - Process continues up the tree
   - Root aggregation = final result

### Final Result Structure

```python
final_result = {
    "summary": "High-level synthesis",
    "detailed_findings": {
        "section_1": "...",
        "section_2": "..."
    },
    "key_insights": [...],
    "recommendations": [...],
    "metadata": {
        "total_nodes": N,
        "llm_calls": M,
        "execution_time": T
    }
}
```

## Complete Flow Example

Let's trace "Research quantum computing applications in healthcare":

### 1. Initialization
```
root (READY) - "Research quantum computing applications in healthcare"
```

### 2. Root Planning (LLM Call #1)
```
root (PLANNING) → DeepResearchPlanner_Agno
Output: 3 subtasks
1. "Research current quantum computing capabilities"
2. "Analyze healthcare challenges suitable for quantum"  
3. "Synthesize findings and identify opportunities"
```

### 3. Sub-node Creation
```
root (PLAN_DONE)
├── root.0 (READY) - Research capabilities
├── root.1 (PENDING) - Analyze challenges [depends on root.0]
└── root.2 (PENDING) - Synthesize [depends on root.0, root.1]
```

### 4. First Sub-task Planning (LLM Call #2)
```
root.0 (PLANNING) → QuantumResearchPlanner_Agno
Output: 2 subtasks
1. "Search recent quantum computing breakthroughs"
2. "Analyze quantum advantage areas"
```

### 5. Leaf Execution (LLM Calls #3-4)
```
root.0.0 (EXECUTING) → WebSearcher_Agno - Search breakthroughs
root.0.1 (EXECUTING) → DataAnalyzer_Agno - Analyze advantages
```

### 6. First Aggregation (LLM Call #5)
```
root.0 (AGGREGATING) → InformationSynthesizer_Agno
Combines search results and analysis
```

### 7. Dependency Resolution
```
root.0 (DONE) → root.1 becomes READY
```

### 8. Continue Processing
```
Similar flow for root.1 and root.2
```

### 9. Final Aggregation (LLM Call #N)
```
root (AGGREGATING) → DeepResearchSynthesizer_Agno
Produces final comprehensive report
```

### 10. Result Delivery
```
Final result returned to user via API/WebSocket
Total LLM calls: ~10-15 depending on complexity
Total time: Varies based on depth and parallelism
```

## Performance Optimizations

### 1. Parallel Execution
- Siblings without dependencies execute concurrently
- Thread pool for LLM calls
- Async I/O throughout

### 2. Context Caching
- CachedContextBuilder reduces redundant processing
- Knowledge store indexes for fast retrieval

### 3. Batching
- BatchedStateManager for efficient updates
- Bulk knowledge store operations

### 4. Smart Context Sizing
- Only includes relevant context
- Summarization for large contexts (>20k words)
- Hierarchical context building

## Monitoring and Debugging

### 1. Trace Management
- Every node execution traced
- Stored in `project_results/traces/`
- Includes timing, context, results

### 2. WebSocket Events
- Real-time status updates
- Progress tracking
- Error notifications

### 3. Logging
- Comprehensive logging at each step
- Different verbosity levels
- Structured log format

## Error Handling

### 1. Node Failure
- Automatic retry (configurable)
- Parent notification
- Graceful degradation

### 2. LLM Failures
- Timeout handling
- Rate limit management  
- Fallback strategies

### 3. System Failures
- State persistence
- Recovery mechanisms
- Partial result handling

## Conclusion

The SentientResearchAgent framework provides a sophisticated hierarchical execution model that:
- Decomposes complex tasks intelligently
- Executes subtasks with specialized agents
- Maintains context throughout the hierarchy
- Aggregates results comprehensively
- Supports human oversight when needed

The system typically makes 5-50+ LLM calls depending on task complexity, with intelligent parallelization and context management ensuring efficient execution.