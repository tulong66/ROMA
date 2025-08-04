# Docker Setup for SentientResearchAgent

## Quick Start

```bash
# Run the setup script
./setup.sh

# Or manually:
cp .env.example .env
# Edit .env with your API keys
docker compose up -d
```

## Architecture

This Docker setup provides:
- **Backend**: Python with PDM (using uv backend) on port 5000
- **Frontend**: React dev server on port 5173

## Configuration

1. Copy `.env.example` to `.env`
2. Add your API keys:
   - `OPENROUTER_API_KEY`
   - `EXA_API_KEY`
   - `GOOGLE_GENAI_API_KEY`

## Commands

```bash
# Start services
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down

# Rebuild after code changes
docker compose build

# Access backend shell
docker compose exec backend bash
```

Or use the Makefile:
```bash
make up      # Start services
make logs    # View logs
make down    # Stop services
make shell   # Backend shell
```

## Development

The setup mounts source directories as volumes, so code changes are reflected immediately:
- Backend source is mounted read-only
- Frontend source is mounted read-only with hot-reload

## Troubleshooting

### Backend not starting
- Check logs: `docker compose logs backend`
- Verify API keys in `.env`
- Ensure port 5000 is not in use

### Frontend not loading
- Check logs: `docker compose logs frontend`
- Ensure backend is healthy first
- Verify port 5173 is not in use

### PDM issues
- The Dockerfile configures PDM to use uv backend automatically
- Dependencies are installed during build