# 🤖 Agent System Deep Dive

## Overview

The Sentient Research Agent framework features a sophisticated multi-agent system built on the **Adapter + AgnoAgent** pattern. This design separates framework integration concerns from LLM interaction logic, creating a flexible and extensible agent architecture.

## 🏗️ Agent Architecture Pattern

### The Adapter + AgnoAgent Design

Every agent in the system consists of two main components:

```python
# Framework Integration Layer
class SomeAdapter(BaseAdapter):
    def __init__(self, agno_agent_instance: AgnoAgent, agent_name: str):
        self.agno_agent = agno_agent_instance
        self.agent_name = agent_name
    
    def process_node(self, node: TaskNode) -> Any:
        # Framework-specific logic
        # Input preparation, error handling, state management
        return self.agno_agent.run(prepared_input)

# LLM Interaction Layer  
agno_agent = AgnoAgent(
    model=LiteLLM(id="openrouter/anthropic/claude-3-7-sonnet"),
    system_message="You are a specialized planning agent...",
    response_model=PlanOutput,  # Structured output schema
    name="CoreResearchPlanner_Agno"
)
```

### Why This Pattern?

1. **Separation of Concerns**: Framework logic vs LLM interaction
2. **Structured Outputs**: Pydantic models ensure consistent responses
3. **Reusability**: AgnoAgents can be used across different adapters
4. **Testability**: Each layer can be tested independently
5. **Extensibility**: Easy to add new agent types

## 🎭 Agent Types and Specializations

### 1. Planning Agents

**Purpose**: Break down complex goals into manageable subtasks

#### Core Research Planner
```python
# From planner_agents.py
PLANNER_SYSTEM_MESSAGE = """You are an expert hierarchical and recursive task decomposition agent. 
Your primary role is to break down complex goals into a sequence of 3 to 6 manageable, 
complementary, and largely mutually exclusive sub-tasks..."""

core_research_planner_agno_agent = AgnoAgent(
    model=LiteLLM(id="openrouter/anthropic/claude-3-7-sonnet"),
    system_message=PLANNER_SYSTEM_MESSAGE,
    response_model=PlanOutput,
    name="CoreResearchPlanner_Agno"
)
```

**Key Capabilities**:
- MECE (Mutually Exclusive, Collectively Exhaustive) decomposition
- Context-aware planning based on execution history
- Sophisticated dependency analysis
- Replanning when tasks fail
- Granularity optimization (3-6 subtasks typically)

**Input Schema**:
```python
class PlannerInput(BaseModel):
    current_task_goal: str
    overall_objective: str
    parent_task_goal: Optional[str]
    planning_depth: int
    execution_history_and_context: ExecutionContext
    replan_request_details: Optional[ReplanRequestDetails]
    global_constraints_or_preferences: List[str]
```

**Output Schema**:
```python
class SubTask(BaseModel):
    goal: str
    task_type: TaskType  # WRITE, THINK, SEARCH
    node_type: NodeType  # PLAN, EXECUTE
    depends_on_indices: List[int]

class PlanOutput(BaseModel):
    subtasks: List[SubTask]
```

### 2. Execution Agents

**Purpose**: Perform specific atomic tasks with domain expertise

#### Search Executor Agent
```python
search_executor_agno_agent = AgnoAgent(
    model=LiteLLM(id="openrouter/anthropic/claude-3-7-sonnet"),
    system_message="""You are a web search strategist and query formulator...""",
    response_model=SearchStrategyOutput,
    name="SearchExecutor_Agno"
)
```

**Specializations**:
- **SearchExecutor**: Formulates search strategies and queries
- **SearchSynthesizer**: Synthesizes and summarizes search results
- **BasicReportWriter**: Generates written content from research

#### Search Synthesizer Agent
```python
search_synthesizer_agno_agent = AgnoAgent(
    model=LiteLLM(id="openrouter/anthropic/claude-3-7-sonnet"),
    system_message="""You are a search results synthesizer. You will be given a 'Research Goal' 
    and 'Raw Search Results'... Extract key facts, figures, and insights...""",
    name="SearchSynthesizer_Agno"
)
```

### 3. Aggregation Agents

**Purpose**: Synthesize results from multiple subtasks

```python
default_aggregator_agno_agent = AgnoAgent(
    model=LiteLLM(id="openrouter/anthropic/claude-3-7-sonnet"),
    system_message="""You are an expert at summarizing and finalizing results.
    You will be provided with a 'Parent Task Goal' and 'Context from Child Tasks'...""",
    name="DefaultAggregator_Agno"
)
```

### 4. Specialized Agents

#### Atomizer Agents
**Purpose**: Optimize task granularity and complexity

```python
default_atomizer_agno_agent = AgnoAgent(
    model=LiteLLM(id="openrouter/anthropic/claude-3-7-sonnet"),
    system_message=ATOMIZER_SYSTEM_MESSAGE,
    response_model=AtomizerDecision,
    name="DefaultAtomizer_Agno"
)
```

#### Plan Modifier Agents
**Purpose**: Handle dynamic plan modifications and HITL feedback

```python
plan_modifier_agno_agent = AgnoAgent(
    model=LiteLLM(id="openrouter/anthropic/claude-3-7-sonnet"),
    system_message=PLAN_MODIFIER_SYSTEM_MESSAGE,
    response_model=PlanOutput,
    name="PlanModifier_Agno"
)
```

#### Custom Search Agents
**Purpose**: Direct integration with search APIs (non-LLM)

```python
class OpenAICustomSearchAdapter(BaseAdapter):
    """Direct search integration without LLM intermediary"""
    
    def __init__(self, model: str = "gpt-4.1"):
        self.model = model
        self.agent_name = "OpenAICustomSearchAdapter"
    
    def process_node(self, node: TaskNode) -> CustomSearcherOutput:
        # Direct API calls to search services
        # No LLM involved in search execution
        pass
```

## 🔄 Agent Registration System

### Configuration-Driven Registration

Agents are registered through a sophisticated configuration system:

```python
# From configurations.py
AGENT_CONFIGURATIONS = [
    AdapterRegistrationConfig(
        adapter_class=PlannerAdapter,
        agno_agent_instance=core_research_planner_agno_agent,
        adapter_agent_name="CoreResearchPlanner",
        registration_keys=[
            RegistrationKey(action_verb="plan", task_type=TaskType.WRITE),
            RegistrationKey(action_verb="plan", task_type=TaskType.SEARCH),
        ],
        named_registrations=["CoreResearchPlanner", "default_planner"],
    )
]
```

### Registry Structure

The framework maintains two registries:

```python
# Action-based lookup: (action_verb, task_type) -> adapter
AGENT_REGISTRY: Dict[Tuple[str, Optional[TaskType]], BaseAdapter] = {}

# Name-based lookup: agent_name -> adapter/agno_agent
NAMED_AGENTS: Dict[str, Any] = {}
```

### Agent Lookup Process

```python
def get_agent_adapter(node: TaskNode, action_verb: str) -> Optional[BaseAdapter]:
    # 1. Try specific agent name if specified
    if node.agent_name:
        return NAMED_AGENTS.get(node.agent_name)
    
    # 2. Try action + task_type combination
    key = (action_verb.lower(), node.task_type)
    if key in AGENT_REGISTRY:
        return AGENT_REGISTRY[key]
    
    # 3. Try action with None task_type (generic)
    generic_key = (action_verb.lower(), None)
    return AGENT_REGISTRY.get(generic_key)
```

## 🛠️ Building Custom Agents

### Step 1: Create the AgnoAgent

```python
from agno.agent import Agent as AgnoAgent
from agno.models.litellm import LiteLLM

my_custom_agno_agent = AgnoAgent(
    model=LiteLLM(id="openrouter/anthropic/claude-3-7-sonnet"),
    system_message="You are a specialized domain expert...",
    response_model=MyCustomOutput,  # Define your output schema
    name="MyCustomAgent_Agno"
)
```

### Step 2: Create the Adapter

```python
from sentientresearchagent.hierarchical_agent_framework.agents.base_adapter import BaseAdapter

class MyCustomAdapter(BaseAdapter):
    def __init__(self, agno_agent_instance: AgnoAgent, agent_name: str):
        super().__init__(agno_agent_instance, agent_name)
    
    def process_node(self, node: TaskNode) -> Any:
        # Prepare input for your AgnoAgent
        custom_input = self._prepare_input(node)
        
        # Execute with the AgnoAgent
        result = self.agno_agent.run(custom_input)
        
        # Process and return result
        return self._process_result(result, node)
    
    def _prepare_input(self, node: TaskNode) -> Dict[str, Any]:
        # Custom input preparation logic
        pass
    
    def _process_result(self, result: Any, node: TaskNode) -> Any:
        # Custom result processing logic
        pass
```

### Step 3: Register the Agent

```python
from sentientresearchagent.hierarchical_agent_framework.agents.configurations import AGENT_CONFIGURATIONS

AGENT_CONFIGURATIONS.append(
    AdapterRegistrationConfig(
        adapter_class=MyCustomAdapter,
        agno_agent_instance=my_custom_agno_agent,
        adapter_agent_name="MyCustomAgent",
        registration_keys=[
            RegistrationKey(action_verb="execute", task_type=TaskType.CUSTOM),
        ],
        named_registrations=["my_custom_agent"],
    )
)
```

## 🔧 Advanced Agent Features

### Structured Output Schemas

All agents use Pydantic models for structured outputs:

```python
class PlanOutput(BaseModel):
    subtasks: List[SubTask]
    reasoning: Optional[str]
    confidence: float = Field(ge=0.0, le=1.0)

class SearchStrategyOutput(BaseModel):
    search_queries: List[str]
    search_strategy: str
    expected_sources: List[str]
```

### Context-Aware Processing

Agents receive rich context for informed decision-making:

```python
class ExecutionContext(BaseModel):
    prior_sibling_task_outputs: List[TaskOutput]
    relevant_ancestor_outputs: List[TaskOutput]
    global_knowledge_base_summary: Optional[str]
```

### Error Handling and Retries

Built-in sophisticated error handling:

```python
class BaseAdapter:
    def process_node_with_retry(self, node: TaskNode) -> Any:
        for attempt in range(self.max_retries):
            try:
                return self.process_node(node)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                self._handle_retry(e, attempt, node)
```

### Human-in-the-Loop Integration

Agents can request human intervention:

```python
def request_human_input(self, node: TaskNode, question: str) -> str:
    # Framework handles HITL coordination
    return self.hitl_coordinator.request_input(node, question)
```

## 🎯 Best Practices

### Agent Design Principles

1. **Single Responsibility**: Each agent should have a clear, specific purpose
2. **Structured Outputs**: Always use Pydantic models for output schemas
3. **Context Awareness**: Leverage available context for better decisions
4. **Error Resilience**: Handle failures gracefully with informative messages
5. **Performance**: Design for concurrent execution where possible

### System Message Guidelines

1. **Be Specific**: Clear instructions for the agent's role and constraints
2. **Include Examples**: Show desired input/output formats
3. **Handle Edge Cases**: Address common failure modes
4. **Context Instructions**: Explain how to use provided context
5. **Output Format**: Specify exactly what output is expected

### Testing Custom Agents

```python
def test_my_custom_agent():
    # Test the AgnoAgent separately
    result = my_custom_agno_agent.run(test_input)
    assert isinstance(result, MyCustomOutput)
    
    # Test the adapter
    adapter = MyCustomAdapter(my_custom_agno_agent, "TestAgent")
    node = create_test_node()
    result = adapter.process_node(node)
    assert result is not None
```

This sophisticated agent system provides the foundation for building powerful, specialized AI agents that can handle complex, domain-specific tasks while maintaining consistency and reliability across the framework. 