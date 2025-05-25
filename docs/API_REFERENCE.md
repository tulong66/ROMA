# 🔌 API Reference

Complete reference for the Sentient Research Agent framework APIs.

## 📚 Table of Contents

- [SimpleSentientAgent](#simplesentientagent) - High-level easy-to-use API
- [Core Framework Classes](#core-framework-classes) - Advanced framework components
- [Agent System](#agent-system) - Sophisticated agent architecture
- [Configuration](#configuration) - Configuration management
- [Utilities](#utilities) - Helper functions and tools

## 🚀 SimpleSentientAgent

The main high-level API for easy interaction with the framework.

### Class: `SimpleSentientAgent`

```python
class SimpleSentientAgent:
    """Simplified API wrapper for the sophisticated agent framework."""
```

#### Constructor

```python
def __init__(self, config: Optional[SentientConfig] = None)
```

**Parameters:**
- `config` (SentientConfig, optional): Configuration object. If None, loads from default sources.

**Example:**
```python
from sentientresearchagent import SimpleSentientAgent
from sentientresearchagent.config import SentientConfig

# With default config
agent = SimpleSentientAgent()

# With custom config
config = SentientConfig.from_yaml("my_config.yaml")
agent = SimpleSentientAgent(config)
```

#### Class Methods

##### `create(config_path=None)`

```python
@classmethod
def create(
    cls, 
    config_path: Optional[Union[str, Path]] = None
) -> "SimpleSentientAgent"
```

**Parameters:**
- `config_path` (str | Path, optional): Path to YAML configuration file

**Returns:**
- `SimpleSentientAgent`: Configured agent instance

**Example:**
```python
# Auto-load configuration
agent = SimpleSentientAgent.create()

# With specific config file
agent = SimpleSentientAgent.create("my_config.yaml")
```

#### Instance Methods

##### `execute(goal, **options)`

```python
def execute(
    self, 
    goal: str, 
    **options
) -> Dict[str, Any]
```

Execute a goal using the sophisticated agent system.

**Parameters:**
- `goal` (str): The high-level goal to achieve
- `**options`: Additional execution options

**Returns:**
```python
{
    'execution_id': str,        # Unique execution identifier
    'goal': str,                # Original goal
    'status': str,              # 'completed' or 'failed'
    'final_output': str,        # Final result text
    'execution_time': float,    # Time in seconds
    'framework_result': Any     # Full framework result object
}
```

**Example:**
```python
result = agent.execute("Research the latest trends in quantum computing")

if result['status'] == 'completed':
    print("Success!")
    print("Output:", result['final_output'])
    print(f"Completed in {result['execution_time']:.2f} seconds")
else:
    print("Failed:", result.get('error'))
```

##### `stream_execution(goal, **options)`

```python
def stream_execution(
    self, 
    goal: str, 
    **options
) -> Iterator[Dict[str, Any]]
```

Execute a goal with real-time progress updates.

**Parameters:**
- `goal` (str): The high-level goal to achieve
- `**options`: Additional execution options

**Yields:**
```python
{
    'execution_id': str,        # Unique execution identifier
    'status': str,              # 'initializing', 'planning', 'executing', 'completed', 'failed'
    'message': str,             # Human-readable status message
    'progress': int,            # Progress percentage (0-100)
    'current_task': str,        # Description of current task
    'final_output': str         # Final output (only on completion)
}
```

**Example:**
```python
for update in agent.stream_execution("Write a comprehensive market analysis"):
    print(f"[{update['status']}] {update['message']} ({update.get('progress', 0)}%)")
    
    if update['status'] == 'completed':
        print("\nFinal Result:")
        print(update['final_output'])
        break
    elif update['status'] == 'failed':
        print("Error:", update.get('error'))
        break
```

## 🧠 Core Framework Classes

Advanced components for sophisticated use cases.

### Class: `TaskNode`

Represents a single task in the hierarchical execution graph.

```python
class TaskNode(BaseModel):
    goal: str                           # Task description
    task_type: TaskType                 # WRITE, THINK, SEARCH, AGGREGATE
    node_type: NodeType                 # PLAN or EXECUTE
    task_id: str                        # Unique identifier
    status: TaskStatus                  # Current execution status
    result: Optional[Any]               # Task result
    layer: int                          # Hierarchical depth
    parent_node_id: Optional[str]       # Parent task ID
    planned_sub_task_ids: List[str]     # Child task IDs
    agent_name: Optional[str]           # Specific agent to use
```

#### Key Methods

```python
def update_status(
    self, 
    new_status: TaskStatus, 
    result: Any = None,
    error_msg: Optional[str] = None
) -> None
```

Update task status with validation and logging.

### Class: `TaskGraph`

Manages the hierarchical graph of tasks.

```python
class TaskGraph:
    def __init__(self):
        self.graphs: Dict[str, nx.DiGraph] = {}
        self.nodes: Dict[str, TaskNode] = {}
        self.root_graph_id: Optional[str] = None
```

#### Key Methods

```python
def add_node_to_graph(self, graph_id: str, node: TaskNode) -> None
def add_edge(self, graph_id: str, u_node_id: str, v_node_id: str) -> None
def get_node(self, node_id: str) -> Optional[TaskNode]
def get_nodes_in_graph(self, graph_id: str) -> List[TaskNode]
```

### Class: `ExecutionEngine`

Orchestrates task execution with the sophisticated agent system.

```python
class ExecutionEngine:
    def __init__(
        self,
        task_graph: TaskGraph,
        node_processor: NodeProcessor,
        state_manager: StateManager,
        knowledge_store: KnowledgeStore
    )
```

#### Key Methods

```python
def initialize_project(self, root_goal: str) -> None
def run_execution_cycle(self) -> Any
```

## 🤖 Agent System

The sophisticated agent architecture with adapters and AgnoAgents.

### Base Classes

#### `BaseAdapter`

Base class for all agent adapters.

```python
class BaseAdapter:
    def __init__(
        self, 
        agno_agent_instance: AgnoAgent, 
        agent_name: str
    ):
        self.agno_agent = agno_agent_instance
        self.agent_name = agent_name
    
    def process_node(self, node: TaskNode) -> Any:
        """Override this method in subclasses"""
        raise NotImplementedError
```

### Adapter Types

#### `PlannerAdapter`

Handles task decomposition using sophisticated planning agents.

```python
class PlannerAdapter(BaseAdapter):
    def process_node(self, node: TaskNode) -> PlanOutput
```

**Available Planning Agents:**
- `SimpleTestPlanner`: General-purpose planning
- `CoreResearchPlanner`: Advanced research planning with sophisticated decomposition

#### `ExecutorAdapter`

Handles task execution using specialized execution agents.

```python
class ExecutorAdapter(BaseAdapter):
    def process_node(self, node: TaskNode) -> Any
```

**Available Execution Agents:**
- `SearchExecutor`: Web search strategy formulation
- `SearchSynthesizer`: Search result synthesis and summarization
- `BasicReportWriter`: Content generation and writing

#### `AggregatorAdapter`

Combines results from multiple subtasks.

```python
class AggregatorAdapter(BaseAdapter):
    def process_node(self, node: TaskNode) -> str
```

#### `OpenAICustomSearchAdapter`

Direct search integration without LLM intermediary.

```python
class OpenAICustomSearchAdapter(BaseAdapter):
    def __init__(self, model: str = "gpt-4.1"):
        self.model = model
        self.agent_name = "OpenAICustomSearchAdapter"
    
    def process_node(self, node: TaskNode) -> CustomSearcherOutput
```

### Agent Registry

#### Functions

```python
def register_agent_adapter(
    adapter: BaseAdapter,
    action_verb: Optional[str] = None,
    task_type: Optional[TaskType] = None,
    name: Optional[str] = None
) -> None
```

Register an adapter in the agent registry.

```python
def get_agent_adapter(
    node: TaskNode, 
    action_verb: str
) -> Optional[BaseAdapter]
```

Retrieve appropriate adapter for a task node.

#### Registry Variables

```python
# Action-based lookup: (action_verb, task_type) -> adapter
AGENT_REGISTRY: Dict[Tuple[str, Optional[TaskType]], BaseAdapter]

# Name-based lookup: agent_name -> adapter
NAMED_AGENTS: Dict[str, Any]
```

### AgnoAgent Integration

The framework uses [Agno](https://github.com/agno-ai/agno) agents for LLM interactions:

```python
from agno.agent import Agent as AgnoAgent
from agno.models.litellm import LiteLLM

# Example sophisticated agent definition
core_research_planner = AgnoAgent(
    model=LiteLLM(id="openrouter/anthropic/claude-3-7-sonnet"),
    system_message="You are an expert hierarchical task decomposition agent...",
    response_model=PlanOutput,  # Structured output with Pydantic
    name="CoreResearchPlanner_Agno"
)
```

## ⚙️ Configuration

### Class: `SentientConfig`

Main configuration class with validation and loading capabilities.

```python
class SentientConfig(BaseModel):
    llm: LLMConfig
    cache: CacheConfig  
    execution: ExecutionConfig
    logging: LoggingConfig
    agents: Dict[str, AgentConfig]
    custom: Dict[str, Any]
```

#### Class Methods

```python
@classmethod
def from_yaml(cls, path: Union[str, Path]) -> "SentientConfig"

@classmethod
def from_env(cls, prefix: str = "SENTIENT_") -> "SentientConfig"

@classmethod
def from_dict(cls, data: Dict[str, Any]) -> "SentientConfig"
```

#### Instance Methods

```python
def to_yaml(self, path: Union[str, Path]) -> None
def to_dict(self) -> Dict[str, Any]
def validate_api_keys(self) -> List[str]
def setup_logging(self) -> None
```

### Configuration Subclasses

#### `LLMConfig`

```python
class LLMConfig(BaseModel):
    provider: str = "openai"
    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    api_key: Optional[str] = None
    timeout: float = 30.0
    max_retries: int = 3
```

#### `ExecutionConfig`

```python
class ExecutionConfig(BaseModel):
    max_concurrent_nodes: int = 5
    max_execution_steps: int = 250
    max_retries: int = 3
    enable_hitl: bool = True
    hitl_timeout_seconds: float = 300.0
```

#### `CacheConfig`

```python
class CacheConfig(BaseModel):
    enabled: bool = True
    ttl_seconds: int = 3600
    max_size: int = 1000
    cache_type: str = "memory"
    cache_dir: Optional[str] = None
```

### Functions

```python
def load_config(
    config_file: Optional[Union[str, Path]] = None,
    use_env: bool = True,
    env_prefix: str = "SENTIENT_"
) -> SentientConfig
```

Intelligent configuration loading with fallbacks.

## 🎯 Types and Enums

### Task Types

```python
class TaskType(str, Enum):
    WRITE = "WRITE"
    THINK = "THINK"
    SEARCH = "SEARCH"
    AGGREGATE = "AGGREGATE"
    CODE_INTERPRET = "CODE_INTERPRET"
    IMAGE_GENERATION = "IMAGE_GENERATION"
```

### Node Types

```python
class NodeType(str, Enum):
    PLAN = "PLAN"        # Needs further decomposition
    EXECUTE = "EXECUTE"  # Atomic task
```

### Task Status

```python
class TaskStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    PLAN_DONE = "PLAN_DONE"
    AGGREGATING = "AGGREGATING"
    DONE = "DONE"
    FAILED = "FAILED"
    NEEDS_REPLAN = "NEEDS_REPLAN"
    CANCELLED = "CANCELLED"
```

## 🔧 Utilities

### Convenience Functions

```python
def quick_research(topic: str, **kwargs) -> str
```

Quick research using default configuration.

```python
def quick_analysis(data_description: str, **kwargs) -> str
```

Quick analysis using default configuration.

### Type Conversion Utilities

```python
def safe_task_status(value: Union[str, TaskStatus]) -> TaskStatus
def safe_node_type(value: Union[str, NodeType]) -> NodeType  
def safe_task_type(value: Union[str, TaskType]) -> TaskType
```

Safe conversion functions with validation.

### Status Checking

```python
def is_terminal_status(status: Union[str, TaskStatus]) -> bool
def is_active_status(status: Union[str, TaskStatus]) -> bool
```

## 🔍 Error Handling

### Exception Classes

```python
class SentientAgentError(Exception):
    """Base exception for framework errors"""
    
class InvalidTaskStateError(SentientAgentError):
    """Task state transition errors"""
    
class TaskError(SentientAgentError):
    """General task execution errors"""
```

### Error Context

All exceptions include helpful context and suggestions:

```python
try:
    result = agent.execute("complex task")
except SentientAgentError as e:
    print("Error:", e)
    if hasattr(e, 'suggestions'):
        print("Suggestions:", e.suggestions)
```

## 📝 Example Usage Patterns

### Basic Research Task

```python
from sentientresearchagent import SimpleSentientAgent

agent = SimpleSentientAgent.create()
result = agent.execute("Research quantum computing applications in finance")

print(result['final_output'])
```

### Advanced Framework Usage

```python
from sentientresearchagent.hierarchical_agent_framework.graph.execution_engine import ExecutionEngine
from sentientresearchagent.hierarchical_agent_framework.agents.registry import get_agent_adapter

# Direct framework interaction
execution_engine = ExecutionEngine(...)
execution_engine.initialize_project("Complex research goal")
result = execution_engine.run_execution_cycle()
```

### Custom Agent Integration

```python
from sentientresearchagent.hierarchical_agent_framework.agents.registry import register_agent_adapter

# Register custom agent
register_agent_adapter(
    adapter=my_custom_adapter,
    action_verb="execute",
    task_type=TaskType.CUSTOM,
    name="my_custom_agent"
)
```

This API provides both simple high-level access and sophisticated low-level control over the framework's capabilities. 