# Sentient Research Agent Documentation

Welcome to the comprehensive documentation for the Sentient Research Agent framework.

## 📖 Table of Contents

- [🏗️ Architecture Overview](ARCHITECTURE.md) - System design and component relationships
- [🚀 Quick Start](QUICKSTART.md) - Get up and running in 5 minutes
- [🤖 Agent System](AGENT_SYSTEM.md) - Understanding the sophisticated agent architecture
- [⚙️ Configuration](CONFIGURATION.md) - Configuration options and setup
- [🔌 API Reference](API_REFERENCE.md) - Complete API documentation
- [🎯 Examples](EXAMPLES.md) - Working examples and use cases
- [🛠️ Custom Agents](CUSTOM_AGENTS.md) - Building your own agents
- [🔧 Troubleshooting](TROUBLESHOOTING.md) - Common issues and solutions
- [🤝 Contributing](CONTRIBUTING.md) - How to contribute to the project

## 🎯 Quick Navigation

**For Users:**
- New to the framework? → [Quick Start](QUICKSTART.md)
- Want to understand how it works? → [Architecture Overview](ARCHITECTURE.md)
- Need specific API details? → [API Reference](API_REFERENCE.md)

**For Developers:**
- Building custom agents? → [Custom Agents](CUSTOM_AGENTS.md) and [Agent System](AGENT_SYSTEM.md)
- Contributing code? → [Contributing](CONTRIBUTING.md)
- Having issues? → [Troubleshooting](TROUBLESHOOTING.md)

## 🏗️ Framework Overview

The Sentient Research Agent framework is built on sophisticated hierarchical task decomposition with these key components:

1. **Hierarchical Task Graph** - Manages complex task breakdowns
2. **Multi-Agent System** - Specialized agents for different task types
3. **Intelligent Execution Engine** - Orchestrates task execution with dependencies
4. **Context & Knowledge Management** - Shares information across tasks
5. **Human-in-the-Loop (HITL)** - Optional human oversight and intervention

## 🤖 Agent Types

The framework includes several sophisticated agent types:

- **Planning Agents** - Break down complex goals (PlannnerAdapter + AgnoAgent)
- **Execution Agents** - Perform specific tasks (ExecutorAdapter + AgnoAgent)  
- **Aggregation Agents** - Synthesize results (AggregatorAdapter + AgnoAgent)
- **Atomizer Agents** - Optimize task granularity (AtomizerAdapter + AgnoAgent)
- **Search Agents** - Specialized web search capabilities
- **Plan Modifier Agents** - Handle plan modifications and replanning

Each agent leverages the sophisticated AgnoAgent framework for LLM interactions with structured outputs. 