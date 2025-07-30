# SentientResearchAgent

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![PDM](https://img.shields.io/badge/PDM-purple)](https://pdm-project.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A hierarchical AI agent framework for sophisticated research and analysis tasks. This framework enables complex multi-step research workflows through intelligent task decomposition, specialized agent collaboration, and human-in-the-loop oversight.

## 🎯 Research Focus

SentientResearchAgent is designed for:
- **Complex Question Answering**: Multi-hop reasoning across diverse information sources
- **Research Automation**: Systematic exploration of topics with citation tracking
- **Evaluation Benchmarking**: Built-in support for standard QA/research datasets
- **Prompt Engineering**: Experiment with different agent configurations and prompts

## 🚀 Quick Start

The easiest way to get started:

```bash
# Clone the repository
git clone https://github.com/yourusername/SentientResearchAgent.git
cd SentientResearchAgent

# Run the setup script
./setup.sh
```

This will prompt you to choose between:
- **Docker Setup** (Recommended) - Isolated environment, one-command setup
- **Native Setup** - Direct installation for development

Both options provide the same functionality. See [docs/SETUP.md](docs/SETUP.md) for detailed instructions.

### Quick Docker Setup

```bash
./setup.sh --docker
# or
make setup-docker
```

### Quick Native Setup (Ubuntu/Debian)

```bash
./setup.sh --native
# or
make setup-native
```

## 🛠️ Manual Installation

For detailed setup instructions, see [docs/SETUP.md](docs/SETUP.md).

### Requirements
- **Python 3.12+** (Native setup installs this automatically on Ubuntu/Debian)
- **Node.js 23.11.0** with npm 10.9.2 (Native setup installs via NVM)
- **PDM** and **UV** package managers (Installed by setup scripts)

### Backend Setup

```bash
# Initialize PDM project
pdm init --non-interactive --python 3.12 --dist
pdm config use_uv true

# Install dependencies
eval "$(pdm venv activate)"
pdm install
```

### Frontend Setup

```bash
cd frontend
npm install
```

### Configuration

1. Copy `.env.example` to `.env`
2. Add your API keys:
   - `OPENROUTER_API_KEY`
   - `EXA_API_KEY`
   - `GOOGLE_GENAI_API_KEY`
3. Update `sentient.yaml` with your preferences

### Running the Application

```bash
# Start the server
python -m sentientresearchagent

# Or with custom config
python -m sentientresearchagent --config sentient.yaml
```

The application will be available at:
- Backend API: http://localhost:5000
- Frontend: http://localhost:5000 (served by backend in production mode)

## 📖 Documentation

- [Detailed Execution Flow](docs/DETAILED_EXECUTION_FLOW.md) - Complete system architecture and flow
- [Docker Setup Guide](docker/README.md) - Docker deployment instructions
- [API Documentation](docs/API.md) - REST and WebSocket API reference

## 🏗️ Architecture Overview

SentientResearchAgent uses a hierarchical task decomposition approach:

```
┌─────────────────┐
│   User Query    │
└────────┬────────┘
         │
┌────────▼────────┐
│  Root Planning  │ ◄── Human Review (Optional)
│     Agent       │
└────────┬────────┘
         │ Decomposes into subtasks
    ┌────┴────┬─────────┬─────────┐
    │         │         │         │
┌───▼──┐ ┌───▼──┐ ┌───▼──┐ ┌───▼──┐
│Agent1│ │Agent2│ │Agent3│ │Agent4│  Parallel Execution
└───┬──┘ └───┬──┘ └───┬──┘ └───┬──┘
    │         │         │         │
    └────┬────┴────┬────┴─────────┘
         │         │
    ┌────▼────┐ ┌──▼──┐
    │Synthesis│ │Cache│
    └────┬────┘ └─────┘
         │
    ┌────▼────┐
    │ Result  │
    └─────────┘
```

Key Components:
1. **Task Decomposition**: Complex queries are broken down into subtasks
2. **Specialized Agents**: Each task type is handled by specialized agents
3. **Parallel Execution**: Independent tasks execute concurrently
4. **Result Aggregation**: Results are synthesized bottom-up
5. **Human-in-the-Loop**: Optional human oversight at key decision points

## 🔧 Key Features

- **Hierarchical Planning**: Automatic task decomposition and planning
- **Multiple Agent Types**: Research, analysis, synthesis, and more
- **Real-time Visualization**: Live task graph updates via WebSocket
- **HITL Integration**: Human oversight and intervention capabilities
- **Caching & Optimization**: Smart caching and parallel execution
- **Comprehensive Logging**: Detailed execution traces and debugging

## 📊 Example Usage

### Basic Research Query

```python
from sentientresearchagent import SentientAgent

# Initialize agent
agent = SentientAgent.create()

# Run a research query
result = await agent.run(
    "What are the main differences between transformer and CNN architectures for computer vision?"
)

print(result)
```

### Using Agent Profiles

```python
from sentientresearchagent import ProfiledSentientAgent

# Use deep research profile for comprehensive analysis
agent = ProfiledSentientAgent.create_with_profile("deep_research_agent")

result = await agent.run(
    "Analyze the environmental impact of lithium-ion battery production"
)
```

### Evaluation on Datasets

```bash
# Run evaluation on a dataset
python evals/evaluation.py --dataset simple_qa --config sentient.yaml

# Grade results
python evals/grade_answers_simple.py results.csv
```

## 🧪 Development

### Running Tests

```bash
# With Docker
cd docker && docker compose exec backend pdm run pytest

# Without Docker
pdm run pytest
```

### Development Mode

```bash
# Backend hot-reload
python -m sentientresearchagent --debug

# Frontend development server
cd frontend && npm run dev
```

### Working with Notebooks

Check the `notebooks/` directory for examples:
- `agent.ipynb` - Basic agent usage examples
- `planner_test.ipynb` - Testing planning capabilities
- `tool_augmented_agents_demo.ipynb` - Tool usage demonstrations

## 📦 Project Structure

```
SentientResearchAgent/
├── src/sentientresearchagent/     # Core Python package
│   ├── core/                      # Core system components
│   ├── hierarchical_agent_framework/  # Agent framework
│   │   ├── agents/                # Agent implementations
│   │   ├── agent_configs/         # Agent configurations & prompts
│   │   ├── graph/                 # Task graph management
│   │   └── node/                  # Task node processing
│   ├── server/                    # Flask API server
│   └── config/                    # Configuration management
├── frontend/                      # React TypeScript frontend
├── evals/                         # Evaluation framework
│   ├── datasets/                  # Benchmark datasets
│   └── evaluation.py             # Main evaluation script
├── notebooks/                     # Example Jupyter notebooks
├── docs/                          # Documentation
├── docker/                        # Docker setup
├── scripts/                       # Utility scripts
│   ├── clean_old_experiments.py  # Clean old experiment results
│   ├── aggregate_results.py      # Aggregate experiment results
│   ├── archive_experiment.py     # Archive important experiments
│   └── migrate_to_new_structure.py # Migrate from old directory structure
├── experiments/                   # Experiment data (git-ignored)
│   ├── configs/                   # Experiment configurations
│   ├── results/                   # Experiment results
│   └── emergency_backups/         # Auto-saved states
└── runtime/                       # Runtime files (git-ignored)
    ├── cache/                     # Agent response cache
    ├── logs/                      # Application logs
    ├── projects/                  # Active project data
    └── temp/                      # Temporary files
```

### Directory Organization

All runtime and output files are now organized into two main directories:
- `runtime/` - Contains all transient runtime files (cache, logs, active projects)
- `experiments/` - Contains experiment configurations and results

This keeps the project root clean and makes it easy to:
- Clean all runtime files: `make clean-runtime`
- Archive experiments: `python scripts/archive_experiment.py`
- Manage old results: `python scripts/clean_old_experiments.py`

## 🔬 Research & Evaluation

### Available Datasets

The framework includes several evaluation datasets in `evals/datasets/`:
- **SimpleQA**: Basic question-answering benchmark
- **FRAMES**: Multi-hop reasoning dataset
- **HLE**: Human-like evaluation tasks
- **Custom**: Add your own datasets in CSV format

### Running Evaluations

```bash
# Basic evaluation
python evals/evaluation.py --dataset simple_qa --num_samples 100

# Full evaluation with custom config
python evals/evaluation.py \
    --dataset frames_benchmark \
    --config sentient.yaml \
    --profile deep_research_agent \
    --output results.csv
```

### Agent Profiles

Pre-configured agent profiles in `src/sentientresearchagent/hierarchical_agent_framework/agent_configs/profiles/`:
- `general_agent.yaml` - Balanced general-purpose configuration
- `deep_research_agent.yaml` - Comprehensive research with multiple passes
- `crypto_analytics_agent.yaml` - Specialized for cryptocurrency analysis

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Quick Contribution Guide

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`pdm run pytest`)
5. Submit a pull request

### Areas for Contribution

- New agent types and profiles
- Additional evaluation datasets
- Performance optimizations
- Documentation improvements
- Bug fixes and enhancements

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details

## 🙏 Acknowledgments

This project builds upon research in hierarchical task decomposition, multi-agent systems, and human-AI collaboration. Special thanks to the open-source AI community for inspiration and tools.

## 📚 Citation

If you use this framework in your research, please cite:

```bibtex
@software{sentientresearchagent,
  title = {SentientResearchAgent: A Hierarchical AI Agent Framework},
  author = {Al-Zubi, Salah},
  year = {2024},
  url = {https://github.com/yourusername/SentientResearchAgent}
}
```
