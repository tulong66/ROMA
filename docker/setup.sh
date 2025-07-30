#!/bin/bash

# Docker setup script for SentientResearchAgent
# Aligned with native setup process using PDM + UV

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Helper functions
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ASCII Banner
cat << "EOF"
  ____            _   _            _   
 / ___|  ___ _ __ | |_(_) ___ _ __ | |_ 
 \___ \ / _ \ '_ \| __| |/ _ \ '_ \| __|
  ___) |  __/ | | | |_| |  __/ | | | |_ 
 |____/ \___|_| |_|\__|_|\___|_| |_|\__|
                                        
 Research Agent - Docker Setup
EOF

echo ""

print_info "Starting Docker setup for SentientResearchAgent..."

# Check Docker
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed"
    echo "Please install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check Docker Compose
if ! docker compose version &> /dev/null 2>&1; then
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed"
        echo "Visit: https://docs.docker.com/compose/install/"
        exit 1
    fi
    COMPOSE_CMD="docker-compose"
else
    COMPOSE_CMD="docker compose"
fi

print_success "Docker and Docker Compose found"

# Setup environment
setup_environment() {
    print_info "Setting up environment configuration..."
    
    # Navigate to project root
    cd "$(dirname "$0")/.."
    
    # Check if .env exists in project root
    if [ ! -f .env ]; then
        if [ -f .env.example ]; then
            cp .env.example .env
            print_info "Created .env file from .env.example"
            print_warning "Please update .env with your API keys!"
        else
            print_warning "No .env.example file found. Please create .env manually."
        fi
    else
        print_info ".env file already exists"
    fi
    
    # Check docker-specific env
    if [ ! -f docker/.env ]; then
        if [ -f docker/.env.example ]; then
            cp docker/.env.example docker/.env
            print_info "Created docker/.env from template"
        else
            # Create docker/.env from main .env
            cp .env docker/.env 2>/dev/null || true
        fi
    fi
    
    # Create necessary directories
    print_info "Creating necessary directories..."
    mkdir -p logs project_results emergency_backups
    
    print_success "Environment setup complete"
}

# Build Docker images
build_docker() {
    print_info "Building Docker images..."
    
    cd docker
    $COMPOSE_CMD build --no-cache
    
    print_success "Docker images built successfully"
}

# Start services
start_services() {
    print_info "Starting services..."
    
    $COMPOSE_CMD up -d
    
    # Wait for services
    print_info "Waiting for services to start..."
    sleep 10
    
    # Check backend health
    if curl -sf http://localhost:5000/api/health > /dev/null; then
        print_success "Backend is healthy"
    else
        print_warning "Backend health check failed - it may still be starting"
        echo "Check logs with: cd docker && $COMPOSE_CMD logs backend"
    fi
    
    # Check frontend
    if curl -sf http://localhost:5173 > /dev/null 2>&1; then
        print_success "Frontend is running"
    else
        print_info "Frontend may still be starting..."
    fi
}

# Display final information
display_info() {
    echo ""
    echo "========================================"
    print_success "Docker Setup Complete!"
    echo "========================================"
    echo ""
    echo "Services:"
    echo "  - Backend API: http://localhost:5000"
    echo "  - Frontend Dev: http://localhost:5173"
    echo ""
    echo "Useful Docker commands:"
    echo "  - View logs:    cd docker && $COMPOSE_CMD logs -f"
    echo "  - Stop:         cd docker && $COMPOSE_CMD down"
    echo "  - Restart:      cd docker && $COMPOSE_CMD restart"
    echo "  - View status:  cd docker && $COMPOSE_CMD ps"
    echo ""
    echo "Development tips:"
    echo "  - Backend hot-reloads on code changes"
    echo "  - Frontend hot-reloads with Vite HMR"
    echo "  - Volumes are mounted for live development"
    echo ""
    
    if [ -f docker/.env ] && grep -q "your_.*_api_key_here" docker/.env; then
        print_warning "Don't forget to add your API keys to docker/.env"
    fi
}

# Main execution
main() {
    setup_environment
    build_docker
    start_services
    display_info
}

# Run main
main