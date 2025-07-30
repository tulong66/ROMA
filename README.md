# 🚀 SentientResearchAgent

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![PDM](https://img.shields.io/badge/PDM-purple)](https://pdm-project.org)
[![Built on AgnoAgents](https://img.shields.io/badge/Built%20on-AgnoAgents-green)](https://github.com/your/agnoagents)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Community](https://img.shields.io/badge/Community-SENT%20Tokens-orange)]()

**Build ANY hierarchical task-solving agent using just three building blocks: Think 🤔, Write ✍️, and Search 🔍**

SentientResearchAgent is a **general-purpose hierarchical task execution framework** that can decompose ANY complex task into manageable subtasks using the MECE (Mutually Exclusive, Collectively Exhaustive) principle. Whether you're building a podcast generator, market analyzer, story writer, or code reviewer - if you can think of it in terms of Think, Write, and Search operations, you can build it here.

## 🎯 What Can You Build?

The only limit is your imagination. Here are just a few examples:

### 🎙️ **Content Creation**
- **Podcast Generator**: Research topics → Generate scripts → Create show notes
- **Blog Automation**: Research → Outline → Write → Edit → Publish
- **Story Writer**: Plot development → Character creation → Chapter writing
- **Video Scripts**: Research → Storyboard → Script → Shot lists

### 📊 **Analysis & Intelligence**
- **Market Analyzer**: Data gathering → Trend analysis → Report generation
- **Crypto Analytics**: On-chain data → Technical analysis → Trading signals
- **Competitor Research**: Information gathering → SWOT analysis → Strategy recommendations
- **Scientific Literature Review**: Paper search → Analysis → Synthesis → Citation management

### 💻 **Technical Applications**
- **Code Generator**: Requirements analysis → Architecture design → Implementation → Documentation
- **API Designer**: Specification → Implementation → Testing → Documentation
- **Documentation Writer**: Code analysis → Structure planning → Content generation

### 🎨 **Creative Workflows**
- **Game Designer**: Concept → Mechanics → Narrative → Level design
- **Art Director**: Mood boards → Style guides → Asset specifications
- **Music Composer**: Theme analysis → Composition → Arrangement

## 🧠 The MECE Framework

Every task in SentientResearchAgent is broken down into three fundamental operations:

### 🤔 **THINK** - Reasoning & Analysis
- Data analysis and interpretation
- Strategic planning and decision making
- Pattern recognition and insights
- Problem solving and evaluation

### ✍️ **WRITE** - Content Generation & Synthesis
- Report writing and documentation
- Creative content generation
- Code implementation
- Summary and synthesis creation

### 🔍 **SEARCH** - Information Retrieval
- Web searches and research
- Database queries
- Literature reviews
- API calls and data fetching

These three operations can be combined recursively to create sophisticated workflows of any complexity.

## ⚡ Key Features

### 🔄 **Recursive Task Decomposition**
- Automatically breaks down complex tasks into subtasks
- Customizable depth control
- Intelligent dependency management
- Parallel execution of independent tasks

### 🤖 **Agent/LLM Agnostic**
- Use ANY LLM provider (OpenAI, Anthropic, Google, local models)
- Built on [AgnoAgents](https://github.com/your/agnoagents) for maximum flexibility
- Multi-modal support out of the box
- Tool integration and MCP support

### 🔍 **Transparent Execution**
- **Stage Tracing**: See exactly what goes into and comes out of every agent
- Debug and optimize your workflows with full visibility
- Understand the reasoning behind every decision
- Perfect for rapid iteration and improvement

### 🌊 **Execution Flow**
- **Top-down decomposition**: Tasks break down from general to specific
- **Bottom-up aggregation**: Results synthesize from specific to general
- **Left-to-right dependencies**: Tasks can depend on siblings for context

### 👥 **Human-in-the-Loop (HITL)**
- Review and modify plans before execution
- Intervene at any stage of the process
- Continuous improvement through human feedback
- Build trust through transparency

### 🎯 **"Vibe Prompting" for Non-Technical Users**
Just describe what you want in natural language, and the framework will figure out the rest:
- "Make me a podcast about AI safety"
- "Analyze the crypto market for the next bull run"
- "Write a fantasy story about dragons in space"
- "Create a business plan for my startup idea"

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/SentientResearchAgent.git
cd SentientResearchAgent

# Run the automated setup
./setup.sh
```

Choose between:
- **Docker Setup** (Recommended) - One-command setup with isolation
- **Native Setup** - Direct installation for development

### Your First Agent in 5 Minutes

```python
from sentientresearchagent import SentientAgent

# Create a podcast generator
agent = SentientAgent.create()

result = await agent.run(
    "Create a 10-minute podcast episode about the future of renewable energy"
)

print(result)  # Your complete podcast script with intro, segments, and outro!
```

### Using Pre-built Profiles

```python
from sentientresearchagent import ProfiledSentientAgent

# Use the crypto analytics profile
agent = ProfiledSentientAgent.create_with_profile("crypto_analytics_agent")

result = await agent.run(
    "Analyze Ethereum's DeFi ecosystem and identify emerging trends"
)
```

## 📖 Documentation

- **[🚀 Introduction](docs/INTRODUCTION.md)** - Understand the vision and possibilities
- **[🍳 Quick Start Cookbook](docs/QUICKSTART_COOKBOOK.md)** - 5-minute agent recipes
- **[🧠 Core Concepts](docs/CORE_CONCEPTS.md)** - Master the MECE framework
- **[💡 Use Cases](docs/USE_CASES.md)** - Real-world applications by industry
- **[🤖 Agents Guide](docs/AGENTS_GUIDE.md)** - Create and customize agents
- **[🔄 Execution Flow](docs/EXECUTION_FLOW.md)** - Understand the task flow
- **[🔍 Stage Tracing](docs/STAGE_TRACING.md)** - Debug and optimize your agents
- **[⚙️ Configuration](docs/CONFIGURATION.md)** - Fine-tune your setup

## 🏗️ Architecture Overview

```
Your Request: "Create a market analysis report"
                    │
                    ▼
           ┌─────────────────┐
           │    ATOMIZER     │ ← "Is this task atomic or needs planning?"
           └────────┬────────┘
                    │ Decides: PLAN node
                    ▼
           ┌─────────────────┐
           │   PLAN NODE     │ ← "Break into subtasks"
           └────────┬────────┘
                    │ Decomposes into
     ┌──────────────┼──────────────┐
     ▼              ▼              ▼
┌─────────┐   ┌─────────┐   ┌─────────┐
│ SEARCH  │   │ SEARCH  │   │ SEARCH  │  ← Each goes through
│ Market  │   │Competitor│  │ Trends  │     atomizer → EXECUTE
│  Data   │   │   Data   │  │  Data   │
└────┬────┘   └────┬────┘   └────┬────┘
     │              │              │        Execute & Return
     ▼              ▼              ▼
[Executor]     [Executor]     [Executor]
     │              │              │
     └──────────────┼──────────────┘
                    ▼
           ┌─────────────────┐
           │   AGGREGATOR    │ ← "Combine all results"
           └────────┬────────┘
                    │ Returns to parent
                    ▼
           ┌─────────────────┐
           │ Final Result    │
           └─────────────────┘

Key Components:
- ATOMIZER: Decides if task needs decomposition (PLAN) or direct execution (EXECUTE)
- PLAN NODE: Breaks complex tasks into subtasks (THINK, WRITE, SEARCH)
- EXECUTE NODE: Directly executes atomic tasks
- AGGREGATOR: Combines results from subtasks bottom-up
```

## 💰 Community & SENT Token Incentives

### 🏆 Build Agents, Earn Rewards!

We're building a vibrant community of agent creators. Share your innovative agents and earn SENT tokens!

**Current Bounties:**
- 🎙️ **Best Podcast Generator**: 10,000 SENT
- 📊 **Best Market Analyzer**: 10,000 SENT  
- 📝 **Best Content Creator**: 10,000 SENT
- 🎮 **Most Creative Use Case**: 10,000 SENT

### How to Participate:
1. Build an awesome agent using SentientResearchAgent
2. Share it with the community
3. Get votes and feedback
4. Earn SENT tokens for popular agents!

**Join our community:**
- [Discord](https://discord.gg/sentientagent)
- [Telegram](https://t.me/sentientagent)
- [Twitter](https://twitter.com/sentientagent)

See [COMMUNITY.md](docs/COMMUNITY.md) for details on the SENT token program.

## 🙏 Acknowledgments

This project was inspired by the hierarchical planning approach described in:

```bibtex
@misc{xiong2025heterogeneousrecursiveplanning,
      title={Beyond Outlining: Heterogeneous Recursive Planning for Long-form Writing with Language Models}, 
      author={Ruibin Xiong and Yimeng Chen and Dmitrii Khizbullin and Mingchen Zhuge and Jürgen Schmidhuber},
      year={2025},
      eprint={2503.08275},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2503.08275}
}
```

Special thanks to the WriteHERE project for pioneering the hierarchical approach to AI task planning.

## 🛠️ Technical Stack

- **Framework**: Built on [AgnoAgents](https://github.com/your/agnoagents)
- **Backend**: Python 3.12+ with FastAPI/Flask
- **Frontend**: React + TypeScript with real-time WebSocket
- **LLM Support**: Any provider via LiteLLM
- **Features**: Multi-modal, tools, MCP, hooks, caching

## 📦 Installation Options

### Quick Start (Recommended)
```bash
./setup.sh
```

### Manual Installation
See [docs/SETUP.md](docs/SETUP.md) for detailed instructions.

### Configuration
1. Copy `.env.example` to `.env`
2. Add your LLM API keys
3. Customize `sentient.yaml` as needed

## 🤝 Contributing

We welcome contributions! Whether it's:
- New agent templates
- Use case examples
- Documentation improvements
- Core framework enhancements

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines.

## 📄 License

MIT License - see [LICENSE](LICENSE) file

## 👨‍💻 Main Contributor

**Salah Al-Zubi** ([@salzubi401](https://github.com/salzubi401))  
Creator and lead developer of SentientResearchAgent

## 🚀 Start Building Today!

```bash
# Install
git clone https://github.com/yourusername/SentientResearchAgent.git
cd SentientResearchAgent
./setup.sh

# Create your first agent
python -m sentientresearchagent

# Or dive into examples
jupyter notebook notebooks/quickstart.ipynb
```

**Remember**: If you can think it, you can build it with Think, Write, and Search! 🚀

---

<p align="center">
  <strong>Join the revolution in hierarchical AI agents. Build something amazing today!</strong>
</p>