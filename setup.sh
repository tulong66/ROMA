#!/bin/bash

# SentientResearchAgent One-Stop Setup Script
# This script sets up the complete production environment

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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
                                        
 Research Agent - Production Setup
EOF

echo ""
print_info "Starting SentientResearchAgent setup..."
echo ""

# Check system requirements
check_requirements() {
    print_info "Checking system requirements..."
    
    # Check for Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        echo "Visit: https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    # Check for Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        echo "Visit: https://docs.docker.com/compose/install/"
        exit 1
    fi
    
    # Check for Git
    if ! command -v git &> /dev/null; then
        print_error "Git is not installed. Please install Git first."
        exit 1
    fi
    
    print_success "All system requirements met!"
}

# Setup environment
setup_environment() {
    print_info "Setting up environment configuration..."
    
    # Check if .env exists
    if [ -f .env ]; then
        print_warning ".env file already exists. Backing up to .env.backup"
        cp .env .env.backup
    fi
    
    # Copy example env if .env doesn't exist
    if [ ! -f .env ]; then
        cp .env.example .env
        print_info "Created .env file from .env.example"
        print_warning "Please update .env with your API keys and configuration!"
    fi
    
    # Create necessary directories
    print_info "Creating necessary directories..."
    mkdir -p data logs cache project_results emergency_backups nginx/ssl
    
    print_success "Environment setup complete!"
}

# Convert from PDM to UV
convert_to_uv() {
    print_info "Converting from PDM to UV package manager..."
    
    # Backup original pyproject.toml
    if [ -f pyproject.toml ]; then
        cp pyproject.toml pyproject.toml.pdm.backup
        print_info "Backed up original pyproject.toml"
    fi
    
    # Use UV version
    if [ -f pyproject.toml.uv ]; then
        cp pyproject.toml.uv pyproject.toml
        print_success "Switched to UV-compatible pyproject.toml"
    fi
    
    # Remove PDM files
    rm -rf .pdm.toml .pdm-python __pypackages__ 2>/dev/null || true
    
    print_success "Conversion to UV complete!"
}

# Build Docker images
build_docker() {
    print_info "Building Docker images..."
    
    # Determine Docker Compose command
    if docker compose version &> /dev/null; then
        DOCKER_COMPOSE="docker compose"
    else
        DOCKER_COMPOSE="docker-compose"
    fi
    
    # Build images
    $DOCKER_COMPOSE build --no-cache
    
    print_success "Docker images built successfully!"
}

# Initialize database (if using PostgreSQL)
init_database() {
    print_info "Initializing database..."
    
    # Start only PostgreSQL service
    $DOCKER_COMPOSE up -d postgres
    
    # Wait for PostgreSQL to be ready
    print_info "Waiting for PostgreSQL to be ready..."
    sleep 10
    
    # TODO: Add database migration scripts here
    # For now, just ensure the service is running
    
    print_success "Database initialized!"
}

# Generate SSL certificates for local development
generate_ssl_certs() {
    print_info "Generating self-signed SSL certificates for local development..."
    
    if [ ! -f nginx/ssl/cert.pem ]; then
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout nginx/ssl/key.pem \
            -out nginx/ssl/cert.pem \
            -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost" \
            2>/dev/null
        
        print_success "SSL certificates generated!"
    else
        print_info "SSL certificates already exist, skipping..."
    fi
}

# Start services
start_services() {
    print_info "Starting all services..."
    
    $DOCKER_COMPOSE up -d
    
    # Wait for services to be healthy
    print_info "Waiting for services to be healthy..."
    sleep 15
    
    # Check health
    if curl -f http://localhost:5000/api/health &> /dev/null; then
        print_success "Backend service is healthy!"
    else
        print_warning "Backend service health check failed. Check logs with: docker-compose logs sentient-backend"
    fi
    
    print_success "All services started!"
}

# Display status and next steps
display_status() {
    echo ""
    echo "========================================"
    print_success "Setup Complete!"
    echo "========================================"
    echo ""
    echo "Services running:"
    echo "  - Backend API: http://localhost:5000"
    echo "  - Frontend: http://localhost:80"
    echo "  - Redis: localhost:6379"
    echo "  - PostgreSQL: localhost:5432"
    echo ""
    echo "Useful commands:"
    echo "  - View logs: docker-compose logs -f"
    echo "  - Stop services: docker-compose down"
    echo "  - Restart services: docker-compose restart"
    echo "  - View status: docker-compose ps"
    echo ""
    print_warning "Don't forget to:"
    echo "  1. Update .env file with your API keys"
    echo "  2. Configure your domain for production deployment"
    echo "  3. Set up proper SSL certificates for production"
    echo ""
}

# Interactive setup
interactive_setup() {
    echo ""
    read -p "Do you want to configure API keys now? (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Opening .env file for editing..."
        ${EDITOR:-nano} .env
    fi
}

# Choose setup method
choose_setup_method() {
    echo ""
    echo "Choose your setup method:"
    echo ""
    echo "  1) Docker Setup (Recommended)"
    echo "     - Isolated environment"
    echo "     - No system dependencies"
    echo "     - One-command setup"
    echo "     - Best for production"
    echo ""
    echo "  2) Native Ubuntu/Debian Setup"
    echo "     - Direct installation"
    echo "     - Full development access"
    echo "     - Manual dependency management"
    echo "     - Best for development"
    echo ""
    echo "Both options provide the same functionality!"
    echo ""
    read -p "Enter your choice (1 or 2): " -n 1 -r
    echo ""
    
    case $REPLY in
        1)
            print_info "Running Docker setup..."
            exec bash docker/setup.sh
            ;;
        2)
            print_info "Running native Ubuntu setup..."
            if [ -f setup_native.sh ]; then
                exec bash setup_native.sh
            else
                print_error "setup_native.sh not found!"
                exit 1
            fi
            ;;
        *)
            print_error "Invalid choice. Please run the script again and select 1 or 2."
            exit 1
            ;;
    esac
}

# Main execution
main() {
    # For backward compatibility, check if --docker flag is passed
    if [[ "$1" == "--docker" ]]; then
        print_info "Running Docker setup..."
        exec bash docker/setup.sh
    fi
    
    # For backward compatibility, check if --native flag is passed
    if [[ "$1" == "--native" ]]; then
        print_info "Running native Ubuntu setup..."
        exec bash setup_native.sh
    fi
    
    # If no flags, show interactive menu
    choose_setup_method
}

# Error handling
trap 'print_error "Setup failed! Check the error messages above."; exit 1' ERR

# Run main function with all arguments
main "$@"