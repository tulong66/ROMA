# 🤖 Complete Guide to Agents

This guide covers everything you need to know about agents in SentientResearchAgent - from using existing agents to creating your own custom ones.

## 📋 Table of Contents

- [What Are Agents?](#-what-are-agents)
- [Agent Types](#-agent-types)
- [Available Agents](#-available-agents)
- [Agent Profiles](#-agent-profiles)
- [Using Agents](#-using-agents)
- [Creating Custom Agents](#-creating-custom-agents)
- [Agent Configuration](#-agent-configuration)
- [Prompt Engineering](#-prompt-engineering)
- [Best Practices](#-best-practices)
- [Advanced Topics](#-advanced-topics)

## 🎯 What Are Agents?

Agents are the intelligent workers in SentientResearchAgent. Each agent:
- **Specializes** in specific types of tasks
- **Encapsulates** prompts, models, and logic
- **Processes** TaskNodes to produce results
- **Integrates** with various LLM providers

Think of agents as specialized employees in your AI company, each expert at their particular job.

## 🏷️ Agent Types

### 1. 🔍 Atomizer Agents

**Purpose**: Determine if a task needs decomposition

```yaml
- name: "SmartAtomizer"
  type: "atomizer"
  description: "Intelligently determines task complexity"
```

**Input/Output**:
```python
Input: TaskNode with goal
Output: {
  "is_atomic": bool,
  "reasoning": "Task requires multiple research steps",
  "refined_goal": "Enhanced version of original goal"
}
```

### 2. 📋 Planner Agents

**Purpose**: Break complex tasks into subtasks

```yaml
- name: "DeepResearchPlanner"
  type: "planner"
  description: "Creates comprehensive research plans"
```

**Input/Output**:
```python
Input: Goal + Context
Output: {
  "subtasks": [
    {"goal": "Research topic A", "type": "SEARCH"},
    {"goal": "Analyze findings", "type": "THINK"},
    {"goal": "Write summary", "type": "WRITE"}
  ],
  "reasoning": "Structured approach for thorough research"
}
```

### 3. ⚡ Executor Agents

**Purpose**: Perform actual work

```yaml
- name: "WebSearcher"
  type: "executor"
  task_type: "SEARCH"
  description: "Searches web for information"
```

**Categories**:
- **Search Executors**: Information retrieval
- **Write Executors**: Content generation
- **Think Executors**: Analysis and reasoning

### 4. 🔄 Aggregator Agents

**Purpose**: Combine results from subtasks

```yaml
- name: "ResearchAggregator"
  type: "aggregator"
  description: "Synthesizes research findings"
```

**Input/Output**:
```python
Input: Array of child results
Output: {
  "synthesis": "Combined findings show...",
  "key_points": ["Point 1", "Point 2"],
  "conclusion": "Overall conclusion"
}
```

### 5. 🔧 Plan Modifier Agents

**Purpose**: Adjust plans based on HITL feedback

```yaml
- name: "PlanModifier"
  type: "plan_modifier"
  description: "Incorporates human feedback into plans"
```

## 📚 Available Agents

### Core Agents

#### Research & Search Agents

| Agent Name | Type | Purpose | Best For |
|------------|------|---------|----------|
| `OpenAICustomSearcher` | Executor | Web search with OpenAI | General research |
| `ExaSearcher` | Executor | Academic/technical search | Scientific papers |
| `EnhancedSearchPlanner` | Planner | Search task decomposition | Complex research |

#### Writing Agents

| Agent Name | Type | Purpose | Best For |
|------------|------|---------|----------|
| `BasicReportWriter` | Executor | General writing | Reports, articles |
| `CreativeWriter` | Executor | Creative content | Stories, scripts |
| `TechnicalWriter` | Executor | Technical docs | Documentation |

#### Analysis Agents

| Agent Name | Type | Purpose | Best For |
|------------|------|---------|----------|
| `BasicReasoningExecutor` | Executor | Logic & analysis | Problem solving |
| `DataAnalyzer` | Executor | Data interpretation | Statistics, trends |
| `StrategyPlanner` | Executor | Strategic thinking | Planning, decisions |

### Specialized Planners

```yaml
# Deep Research Planner - Comprehensive research
DeepResearchPlanner:
  - Multi-stage research approach
  - Citation tracking
  - Fact verification

# Enhanced Search Planner - Optimized for search
EnhancedSearchPlanner:
  - Date-aware searching
  - Parallel search strategies
  - Source diversity

# Creative Project Planner - Creative workflows
CreativeProjectPlanner:
  - Ideation phases
  - Iterative refinement
  - Multi-modal outputs
```

## 🎨 Agent Profiles

Agent profiles are pre-configured collections of agents optimized for specific use cases.

### Available Profiles

#### 1. 🔬 Deep Research Agent

```yaml
profile: deep_research_agent
purpose: "Comprehensive research with citations"
agents:
  root_planner: "DeepResearchPlanner"
  search_executor: "OpenAICustomSearcher"
  aggregator: "ResearchAggregator"
```

**Best for**:
- Academic research
- Market analysis
- Fact-checking
- Literature reviews

#### 2. 🌐 General Agent

```yaml
profile: general_agent
purpose: "Balanced general-purpose tasks"
agents:
  planner: "CoreResearchPlanner"
  executor: "BasicReasoningExecutor"
  aggregator: "GeneralAggregator"
```

**Best for**:
- Mixed tasks
- Quick queries
- General Q&A
- Exploratory work

#### 3. 💰 Crypto Analytics Agent

```yaml
profile: crypto_analytics_agent
purpose: "Cryptocurrency analysis"
agents:
  planner: "CryptoAnalysisPlanner"
  data_fetcher: "CryptoDataSearcher"
  analyzer: "TechnicalAnalyzer"
```

**Best for**:
- Market analysis
- Token research
- DeFi protocols
- Trading strategies

### Using Profiles

```python
# Python API
from sentientresearchagent import ProfiledSentientAgent

agent = ProfiledSentientAgent.create_with_profile("deep_research_agent")
result = await agent.run("Research quantum computing applications")
```

```bash
# CLI
python -m sentientresearchagent --profile deep_research_agent
```

## 🔨 Using Agents

### Direct Agent Usage

```python
# Get specific agent
from sentientresearchagent.agents import AgentRegistry

registry = AgentRegistry()
search_agent = registry.get_agent(
    action_verb="execute",
    task_type="SEARCH"
)

# Use agent
result = await search_agent.process(task_node)
```

### Agent Selection Strategy

The framework automatically selects agents based on:

1. **Task Type** (SEARCH, WRITE, THINK)
2. **Action Verb** (plan, execute, aggregate)
3. **Profile Configuration**
4. **Node Context**

### Context Passing

Agents receive context automatically:

```python
{
  "task": task_node,
  "relevant_results": [...],  # From siblings/parents
  "overall_objective": "...",  # Root goal
  "constraints": [...],        # Any limitations
  "user_preferences": {...}    # Style, length, etc.
}
```

## 🛠️ Creating Custom Agents

### Method 1: YAML Configuration

Create a new agent in `agents.yaml`:

```yaml
agents:
  - name: "MyCustomSearcher"
    type: "executor"
    adapter_class: "ExecutorAdapter"
    description: "Specialized search for my domain"
    model:
      provider: "litellm"
      model_id: "gpt-4"
      temperature: 0.3
    prompt_source: "prompts.executor_prompts.MY_CUSTOM_PROMPT"
    registration:
      action_keys:
        - action_verb: "execute"
          task_type: "SEARCH"
      named_keys: ["MyCustomSearcher", "custom_search"]
    tools:  # Optional tool configuration
      - name: "web_search"
        config:
          api_key: "${EXA_API_KEY}"
    enabled: true
```

### Method 2: Python Code

Create a custom agent class:

```python
from sentientresearchagent.agents import BaseAgent
from typing import Dict, Any

class MyCustomAgent(BaseAgent):
    """Custom agent for specialized tasks"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "MyCustomAgent"
        self.description = "Handles my specific use case"
        
    async def process(self, task_node: TaskNode, context: Dict) -> Any:
        """Process a task node"""
        # Your custom logic here
        prompt = self._build_prompt(task_node, context)
        
        # Call LLM
        response = await self.llm.generate(
            prompt=prompt,
            temperature=0.5
        )
        
        # Process and return result
        return self._parse_response(response)
    
    def _build_prompt(self, task_node: TaskNode, context: Dict) -> str:
        """Build custom prompt"""
        return f"""
        Task: {task_node.goal}
        Context: {context.get('relevant_results', [])}
        
        Please complete this task with attention to detail.
        """
```

### Method 3: Extending Existing Agents

```python
from sentientresearchagent.agents import WebSearcher

class EnhancedWebSearcher(WebSearcher):
    """Enhanced version with additional capabilities"""
    
    async def process(self, task_node: TaskNode, context: Dict) -> Any:
        # Add pre-processing
        enhanced_query = self._enhance_query(task_node.goal)
        
        # Use parent functionality
        results = await super().process(task_node, context)
        
        # Add post-processing
        return self._filter_and_rank(results)
```

## ⚙️ Agent Configuration

### Model Configuration

```yaml
model:
  provider: "litellm"        # or "openai", "anthropic", etc.
  model_id: "gpt-4"          # Specific model
  temperature: 0.7           # Creativity level
  max_tokens: 2000           # Response length
  top_p: 0.9                 # Nucleus sampling
  frequency_penalty: 0.1     # Reduce repetition
```

### Tool Configuration

```yaml
tools:
  - name: "web_search"
    type: "exa"
    config:
      num_results: 10
      search_type: "neural"
      
  - name: "calculator"
    type: "python"
    config:
      timeout: 30
```

### Response Models

Define structured outputs using Pydantic:

```python
from pydantic import BaseModel
from typing import List

class SearchResult(BaseModel):
    query: str
    results: List[Dict[str, Any]]
    confidence: float
    sources: List[str]

# In agent config
response_model: "SearchResult"
```

## 📝 Prompt Engineering

### System Prompts

Define agent behavior and expertise:

```python
EXPERT_RESEARCHER_PROMPT = """
You are an expert research analyst with deep knowledge across multiple domains.
Your strengths include:
- Finding authoritative sources
- Synthesizing complex information
- Identifying key insights
- Fact-checking and verification

Always cite your sources and indicate confidence levels.
"""
```

### Task Prompts

Structure task execution:

```python
SEARCH_TASK_PROMPT = """
Goal: {goal}
Context: {context}
Constraints: {constraints}

Please search for information addressing this goal.
Focus on:
1. Recent, authoritative sources
2. Multiple perspectives
3. Factual accuracy

Format your response as:
- Key Findings: ...
- Sources: ...
- Confidence: ...
"""
```

### Dynamic Prompts

Adapt based on context:

```python
def build_prompt(task_node: TaskNode, context: Dict) -> str:
    base_prompt = SEARCH_TASK_PROMPT
    
    # Add date awareness
    if "current" in task_node.goal or "latest" in task_node.goal:
        base_prompt += "\nPrioritize information from 2024."
    
    # Add domain expertise
    if "medical" in task_node.goal:
        base_prompt += "\nUse medical and scientific sources."
    
    return base_prompt.format(
        goal=task_node.goal,
        context=context
    )
```

## 💡 Best Practices

### 1. Agent Design

**Do**:
- Keep agents focused on one capability
- Use descriptive names
- Document expected inputs/outputs
- Handle errors gracefully

**Don't**:
- Create overly complex agents
- Hardcode specific values
- Ignore context
- Skip validation

### 2. Prompt Engineering

**Do**:
- Be specific and clear
- Provide examples when helpful
- Set clear output formats
- Include confidence indicators

**Don't**:
- Use ambiguous language
- Create overly long prompts
- Repeat instructions
- Assume context

### 3. Performance Optimization

```yaml
# Cache expensive operations
cache:
  enabled: true
  ttl_seconds: 3600

# Batch similar requests
batch_size: 5
batch_timeout_ms: 100

# Use appropriate models
model_selection:
  simple_tasks: "gpt-3.5-turbo"
  complex_tasks: "gpt-4"
  creative_tasks: "claude-3"
```

### 4. Error Handling

```python
class RobustAgent(BaseAgent):
    async def process(self, task_node: TaskNode, context: Dict) -> Any:
        try:
            result = await self._execute_task(task_node, context)
            return result
        except RateLimitError:
            await asyncio.sleep(60)
            return await self.process(task_node, context)
        except Exception as e:
            logger.error(f"Agent error: {e}")
            return {
                "error": str(e),
                "fallback": self._generate_fallback(task_node)
            }
```

## 🚀 Advanced Topics

### Multi-Agent Collaboration

```python
class CollaborativeAgent(BaseAgent):
    def __init__(self, collaborators: List[BaseAgent]):
        self.collaborators = collaborators
    
    async def process(self, task_node: TaskNode, context: Dict) -> Any:
        # Get input from collaborators
        insights = []
        for agent in self.collaborators:
            insight = await agent.analyze(task_node, context)
            insights.append(insight)
        
        # Synthesize collaborative result
        return self._synthesize(insights)
```

### Adaptive Agents

```python
class AdaptiveAgent(BaseAgent):
    def __init__(self):
        self.performance_history = []
    
    async def process(self, task_node: TaskNode, context: Dict) -> Any:
        # Select strategy based on past performance
        strategy = self._select_strategy(task_node)
        
        # Execute with monitoring
        start_time = time.time()
        result = await self._execute_strategy(strategy, task_node)
        execution_time = time.time() - start_time
        
        # Learn from execution
        self._update_performance(strategy, execution_time, result)
        
        return result
```

### Tool-Augmented Agents

```python
class ToolAugmentedAgent(BaseAgent):
    def __init__(self, tools: List[Tool]):
        self.tools = {tool.name: tool for tool in tools}
    
    async def process(self, task_node: TaskNode, context: Dict) -> Any:
        # Determine required tools
        required_tools = self._analyze_tool_needs(task_node)
        
        # Execute with tools
        tool_results = {}
        for tool_name in required_tools:
            tool = self.tools[tool_name]
            tool_results[tool_name] = await tool.execute(task_node)
        
        # Combine tool results with LLM reasoning
        return await self._reason_with_tools(task_node, tool_results)
```

### Agent Monitoring

```python
class MonitoredAgent(BaseAgent):
    def __init__(self):
        self.metrics = {
            "total_calls": 0,
            "success_rate": 0.0,
            "avg_response_time": 0.0,
            "error_types": {}
        }
    
    async def process(self, task_node: TaskNode, context: Dict) -> Any:
        self.metrics["total_calls"] += 1
        
        try:
            result = await self._execute(task_node, context)
            self._update_success_metrics()
            return result
        except Exception as e:
            self._track_error(e)
            raise
```

## 📚 Example: Creating a Domain-Specific Agent

Let's create a specialized agent for analyzing scientific papers:

```yaml
# In agents.yaml
agents:
  - name: "ScientificPaperAnalyzer"
    type: "executor"
    adapter_class: "ExecutorAdapter"
    description: "Analyzes scientific papers for key findings"
    model:
      provider: "litellm"
      model_id: "claude-3-opus"
      temperature: 0.2  # Low for accuracy
    
    prompt_source: "custom_prompts.SCIENTIFIC_ANALYZER"
    
    response_model: "ScientificAnalysis"
    
    tools:
      - name: "arxiv_search"
        type: "api"
      - name: "citation_checker"
        type: "custom"
    
    registration:
      action_keys:
        - action_verb: "execute"
          task_type: "THINK"
      named_keys: ["ScientificAnalyzer", "paper_analyzer"]
    
    config:
      focus_areas:
        - methodology
        - results
        - limitations
        - future_work
      citation_threshold: 10
      confidence_required: 0.8
```

## 🎯 Next Steps

- Explore [existing agents](../src/sentientresearchagent/agents/)
- Study [agent configurations](../src/sentientresearchagent/agent_configs/)
- Review [prompt templates](../src/sentientresearchagent/agent_configs/prompts/)
- Try creating your own agent!

Remember: Great agents are built through iteration. Start simple, test thoroughly, and refine based on results. 🚀