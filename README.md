# SentientResearchAgent

A hierarchical AI agent framework for sophisticated research and analysis tasks.

## 🚀 Quick Start with Docker

The easiest way to get started is using our Docker setup:

```bash
cd docker
./setup.sh
```

This will set up both backend and frontend services with all dependencies. See [docker/README.md](docker/README.md) for detailed instructions.

## 🛠️ Manual Installation

If you prefer to run without Docker, you'll need Python 3.12+ and Node.js 20+.

### Backend Setup

```bash
# Install PDM
pip install pdm

# Configure PDM to use uv backend (faster)
pdm config use_uv true

# Install dependencies
pdm install
```

### Frontend Setup

```bash
cd frontend
npm install
npm run build
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

## 📦 Project Structure

```
SentientResearchAgent/
├── src/sentientresearchagent/     # Core Python package
│   ├── core/                      # Core system components
│   ├── hierarchical_agent_framework/  # Agent framework
│   ├── server/                    # Flask API server
│   └── config/                    # Configuration management
├── frontend/                      # React TypeScript frontend
├── docs/                          # Documentation
├── docker/                        # Docker setup and configuration
└── scripts/                       # Utility scripts
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details
