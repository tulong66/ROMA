#!/bin/bash

# Simple setup script for SentientResearchAgent

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "🚀 SentientResearchAgent Docker Setup"
echo "===================================="
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed${NC}"
    echo "Please install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check Docker Compose
if ! docker compose version &> /dev/null 2>&1; then
    if ! command -v docker-compose &> /dev/null; then
        echo -e "${RED}❌ Docker Compose is not installed${NC}"
        exit 1
    fi
    COMPOSE_CMD="docker-compose"
else
    COMPOSE_CMD="docker compose"
fi

echo -e "${GREEN}✓ Docker and Docker Compose found${NC}"

# Setup environment
if [ ! -f docker/.env ]; then
    cp docker/.env.example docker/.env
    echo -e "${YELLOW}⚠️  Created docker/.env from template${NC}"
    echo -e "${YELLOW}   Please edit docker/.env with your API keys!${NC}"
else
    echo -e "${GREEN}✓ docker/.env already exists${NC}"
fi

# Create necessary directories
echo "Creating directories..."
mkdir -p logs project_results emergency_backups

# Build and start
echo ""
echo "Building Docker images..."
cd docker
$COMPOSE_CMD build

echo ""
echo "Starting services..."
$COMPOSE_CMD up -d

# Wait for services
echo ""
echo "Waiting for services to start..."
sleep 5

# Check health
if curl -sf http://localhost:5000/api/health > /dev/null; then
    echo -e "${GREEN}✓ Backend is healthy${NC}"
else
    echo -e "${YELLOW}⚠️  Backend health check failed${NC}"
fi

echo ""
echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo "Services:"
echo "  Backend API: http://localhost:5000"
echo "  Frontend Dev: http://localhost:5173"
echo ""
echo "Commands:"
echo "  View logs:    cd docker && docker compose logs -f"
echo "  Stop:         cd docker && docker compose down"
echo "  Restart:      cd docker && docker compose restart"
echo ""

if grep -q "your_.*_api_key_here" docker/.env; then
    echo -e "${YELLOW}⚠️  Don't forget to add your API keys to docker/.env${NC}"
fi