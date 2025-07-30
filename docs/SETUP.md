# SentientResearchAgent Setup Guide

This guide provides detailed instructions for setting up SentientResearchAgent using either Docker (recommended for production) or native installation (recommended for development).

## Prerequisites

### For Docker Setup
- Docker and Docker Compose installed
- Git

### For Native Setup (Ubuntu/Debian)
- Ubuntu 20.04+ or Debian 11+
- sudo privileges
- Git

## Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/SentientResearchAgent.git
cd SentientResearchAgent

# Run the setup script
./setup.sh
```

The setup script will prompt you to choose between:
1. **Docker setup** - Containerized environment, best for production
2. **Native setup** - Direct installation, best for development

## Docker Setup

### Quick Setup
```bash
./setup.sh --docker
# or
make setup-docker
```

### What It Does
1. Checks Docker and Docker Compose installation
2. Creates `.env` file from template
3. Builds optimized Docker images using UV for fast dependency installation
4. Starts all services (backend and frontend)
5. Verifies health of services

### Docker Commands
```bash
# View logs
cd docker && docker compose logs -f

# Stop services
cd docker && docker compose down

# Restart services
cd docker && docker compose restart

# View status
cd docker && docker compose ps

# Rebuild after changes
cd docker && docker compose build
```

### Docker Architecture
- **Backend**: Python 3.12 with UV package manager
- **Frontend**: Node.js 23.11.0 with npm 10.9.2
- **Volumes**: Mounted for live development
- **Ports**: Backend (5000), Frontend (5173)

## Native Setup (Ubuntu/Debian)

### Quick Setup
```bash
./setup.sh --native
# or
make setup-native
```

### What It Does
1. Installs Python 3.12 from deadsnakes PPA
2. Installs PDM and UV package managers
3. Installs NVM, Node.js 23.11.0, and npm 10.9.2
4. Initializes PDM project with UV backend
5. Creates virtual environment and installs dependencies
6. Installs frontend dependencies
7. Creates necessary directories

### Manual Steps

#### 1. Install Python 3.12
```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.12 python3.12-venv python3.12-dev
```

#### 2. Install PDM and UV
```bash
# Install PDM
curl -sSL https://pdm-project.org/install-pdm.py | python3 -

# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add to PATH (add to ~/.bashrc)
export PATH="$HOME/.local/bin:$PATH"
source "$HOME/.cargo/env"
```

#### 3. Install Node.js
```bash
# Install NVM
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc

# Install Node.js and npm
nvm install 23.11.0
nvm use 23.11.0
npm install -g npm@10.9.2
```

#### 4. Setup Project
```bash
# Initialize PDM
pdm init --non-interactive --python 3.12 --dist
pdm config use_uv true

# Install dependencies
eval "$(pdm venv activate)"
pdm install

# Install frontend
cd frontend && npm install
```

### Running the Application

#### Using Screen (Recommended)
```bash
# Start backend
screen -S backend_server
eval "$(pdm venv activate)"
python -m sentientresearchagent
# Press Ctrl+A, then D to detach

# Start frontend
screen -S frontend_server
cd frontend && npm run dev
# Press Ctrl+A, then D to detach

# View screens
screen -ls

# Reattach to screen
screen -r backend_server
```

#### Direct Run
```bash
# Terminal 1 - Backend
eval "$(pdm venv activate)"
python -m sentientresearchagent

# Terminal 2 - Frontend
cd frontend && npm run dev
```

## Environment Configuration

### API Keys
Both setup methods require API keys in the `.env` file:

```bash
# OpenRouter API Key (required)
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Optional API Keys
EXA_API_KEY=your_exa_api_key_here
GOOGLE_GENAI_API_KEY=your_google_genai_api_key_here
```

### Configuration Files
- **Main config**: `sentient.yaml`
- **Environment**: `.env` (created from `.env.example`)
- **Agent profiles**: `src/sentientresearchagent/hierarchical_agent_framework/agent_configs/profiles/`

## Troubleshooting

### Common Issues

#### Docker Issues
- **Port conflicts**: Ensure ports 5000 and 5173 are free
- **Permission denied**: Run Docker commands with sudo or add user to docker group
- **Build failures**: Clear Docker cache with `docker system prune`

#### Native Setup Issues
- **Python version**: Ensure Python 3.12 is active
- **PDM not found**: Add `~/.local/bin` to PATH
- **UV not found**: Source `~/.cargo/env`
- **Node version**: Use `nvm use 23.11.0` to switch versions

### Health Checks
```bash
# Check backend
curl http://localhost:5000/api/health

# Check frontend
curl http://localhost:5173
```

### Logs
- **Docker logs**: `cd docker && docker compose logs -f`
- **Native logs**: Check `logs/` directory in project root

## Development Workflow

### Making Changes
1. **Backend**: Changes in `src/` are auto-reloaded
2. **Frontend**: Vite HMR provides instant updates
3. **Config**: Restart services after changing `sentient.yaml`

### Using Different Agent Profiles
```bash
# With specific config
python -m sentientresearchagent --config sentient.yaml

# With different profile
python -m sentientresearchagent --profile deep_research_agent
```

## Production Deployment

For production, use Docker setup with:
1. Proper SSL certificates (replace self-signed)
2. Environment-specific `.env` file
3. Production-grade database (if using PostgreSQL)
4. Reverse proxy (nginx) configuration
5. Monitoring and logging setup

## Additional Resources

- [Project README](../README.md)
- [CLAUDE.md](../CLAUDE.md) - AI assistant instructions
- [API Documentation](./API.md)
- [Architecture Overview](./ARCHITECTURE.md)

## Support

If you encounter issues:
1. Check the troubleshooting section
2. Review logs for error messages
3. Ensure all prerequisites are met
4. Open an issue on GitHub with details