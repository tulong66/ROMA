#!/bin/bash

# SentientResearchAgent Unified Setup Script
# Supports both Docker and Native installation (macOS and Ubuntu/Debian)

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

# OS detection helpers
OS_FAMILY="unknown"

detect_os() {
    uname_s="$(uname -s 2>/dev/null || echo "")"
    case "$uname_s" in
        Darwin)
            OS_FAMILY="macos"
            ;;
        Linux)
            if [[ -f /etc/debian_version ]]; then
                OS_FAMILY="debian"
            else
                OS_FAMILY="linux"
            fi
            ;;
        *)
            OS_FAMILY="unknown"
            ;;
    esac
}

open_url() {
    local url="$1"
    detect_os
    case "$OS_FAMILY" in
        macos)
            command -v open >/dev/null 2>&1 && open "$url" || true
            ;;
        debian|linux)
            command -v xdg-open >/dev/null 2>&1 && xdg-open "$url" >/dev/null 2>&1 || true
            ;;
        *)
            ;;
    esac
}

get_shell_profile() {
    # Prefer zsh on macOS, otherwise bash
    if [ -n "$ZSH_VERSION" ] || [ "$(basename "$SHELL")" = "zsh" ]; then
        echo "$HOME/.zshrc"
    else
        echo "$HOME/.bashrc"
    fi
}

append_to_profile_once() {
    local line="$1"
    local profile
    profile="$(get_shell_profile)"
    touch "$profile"
    if ! grep -Fqx "$line" "$profile" 2>/dev/null; then
        echo "$line" >> "$profile"
    fi
}

# ASCII Banner
show_banner() {
    cat << "EOF"
  ____            _   _            _   
 / ___|  ___ _ __ | |_(_) ___ _ __ | |_ 
 \___ \ / _ \ '_ \| __| |/ _ \ '_ \| __|
  ___) |  __/ | | | |_| |  __/ | | | |_ 
 |____/ \___|_| |_|\__|_|\___|_| |_|\__|
                                        
 Research Agent - Setup
EOF
    echo ""
}

# ============================================
# DOCKER SETUP FUNCTIONS
# ============================================

docker_check_requirements() {
    print_info "Checking Docker requirements..."
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        echo "Please install Docker: https://docs.docker.com/get-docker/"
        return 1
    fi
    
    if ! docker compose version &> /dev/null 2>&1; then
        if ! command -v docker-compose &> /dev/null; then
            print_error "Docker Compose is not installed"
            echo "Visit: https://docs.docker.com/compose/install/"
            return 1
        fi
        COMPOSE_CMD="docker-compose"
    else
        COMPOSE_CMD="docker compose"
    fi
    
    print_success "Docker and Docker Compose found"
    return 0
}

docker_setup_environment() {
    print_info "Setting up Docker environment..."
    
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

docker_build() {
    print_info "Building Docker images..."
    
    cd docker
    $COMPOSE_CMD build --no-cache
    cd ..
    
    print_success "Docker images built successfully"
}

docker_start() {
    print_info "Starting Docker services..."
    
    (cd docker && $COMPOSE_CMD up -d)
    
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
    if curl -sf http://localhost:3000 > /dev/null 2>&1; then
        print_success "Frontend is running on http://localhost:3000"
    else
        print_info "Frontend may still be starting..."
    fi
    
    # Auto-open browser for Docker frontend
    open_url "http://localhost:3000"
}

docker_setup() {
    print_info "Starting Docker setup..."
    
    if ! docker_check_requirements; then
        return 1
    fi
    
    docker_setup_environment
    docker_build
    docker_start
    
    echo ""
    echo "========================================"
    print_success "Docker Setup Complete!"
    echo "========================================"
    echo ""
    echo "Services:"
    echo "  - Backend API: http://localhost:5000"
    echo "  - Frontend Dev: http://localhost:3000"
    echo ""
    echo "Useful Docker commands:"
    echo "  - View logs:    cd docker && $COMPOSE_CMD logs -f"
    echo "  - Stop:         cd docker && $COMPOSE_CMD down"
    echo "  - Restart:      cd docker && $COMPOSE_CMD restart"
    echo "  - View status:  cd docker && $COMPOSE_CMD ps"
    echo ""
    
    if [ -f docker/.env ] && grep -q "your_.*_api_key_here" docker/.env; then
        print_warning "Don't forget to add your API keys to docker/.env"
    fi
}

# ============================================
# NATIVE SETUP FUNCTIONS (Shared)
# ============================================

native_install_pdm_uv() {
    print_info "Installing PDM and UV package managers..."
    
    # Install PDM
    if ! command -v pdm &> /dev/null; then
        print_info "Installing PDM..."
        curl -sSL https://pdm-project.org/install-pdm.py | python3 -
        
        # Add PDM to PATH for current session and shell profile
        export PATH="$HOME/.local/bin:$PATH"
        append_to_profile_once 'export PATH="$HOME/.local/bin:$PATH"'
    else
        print_success "PDM is already installed"
    fi
    
    # Install UV
    if ! command -v uv &> /dev/null; then
        print_info "Installing UV..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        
        # Try to source cargo env if available (harmless if not)
        if [ -f "$HOME/.cargo/env" ]; then
            # shellcheck source=/dev/null
            source "$HOME/.cargo/env"
            append_to_profile_once 'source "$HOME/.cargo/env"'
        fi
        # Ensure ~/.local/bin is on PATH (uv may be installed there)
        append_to_profile_once 'export PATH="$HOME/.local/bin:$PATH"'
        export PATH="$HOME/.local/bin:$PATH"
    else
        print_success "UV is already installed"
    fi
    
    print_success "PDM and UV installed successfully"
}

native_install_node() {
    print_info "Installing NVM and Node.js..."
    
    # Install NVM
    if [ ! -d "$HOME/.nvm" ]; then
        print_info "Installing NVM..."
        curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
        
        # Load NVM
        export NVM_DIR="$HOME/.nvm"
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
        append_to_profile_once 'export NVM_DIR="$HOME/.nvm"'
        append_to_profile_once '[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"'
    else
        print_success "NVM is already installed"
        # Load NVM
        export NVM_DIR="$HOME/.nvm"
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    fi
    
    # Install Node.js 23.11.0 with fallback to LTS if unavailable
    print_info "Installing Node.js v23.11.0..."
    if ! nvm install 23.11.0; then
        print_warning "Node v23.11.0 not available; falling back to latest LTS"
        nvm install --lts
        nvm use --lts
    else
        nvm use 23.11.0
    fi
    
    # Install specific npm version
    print_info "Installing npm v10.9.2..."
    npm install -g npm@10.9.2 || print_warning "Could not set npm to v10.9.2; continuing."
    
    # Verify versions
    NODE_VERSION=$(node -v || echo "unknown")
    NPM_VERSION=$(npm -v || echo "unknown")
    
    print_success "Node.js version: $NODE_VERSION, npm version: $NPM_VERSION"
}

native_setup_project() {
    print_info "Setting up project with PDM..."
    
    # Check if we're in the project directory
    if [ ! -f "pyproject.toml" ]; then
        print_error "Please run this script from the SentientResearchAgent project root directory"
        return 1
    fi
    
    # Initialize PDM if not already initialized
    if [ ! -f "pdm.lock" ]; then
        print_info "Initializing PDM project..."
        pdm init --non-interactive --python 3.12 --dist
    fi
    
    # Configure PDM to use UV
    print_info "Configuring PDM to use UV backend..."
    pdm config use_uv true
    
    # Create and activate virtual environment
    print_info "Creating virtual environment..."
    pdm venv create --python 3.12 || true
    
    # Install dependencies
    print_info "Installing Python dependencies..."
    eval "$(pdm venv activate)"
    pdm install
    
    print_success "Project setup complete"
}

native_install_frontend() {
    print_info "Installing frontend dependencies..."
    
    # Check if frontend directory exists
    if [ ! -d "frontend" ]; then
        print_error "Frontend directory not found"
        return 1
    fi
    
    cd frontend
    
    # Install dependencies
    print_info "Running npm install..."
    npm install
    
    cd ..
    
    print_success "Frontend dependencies installed"
}

native_setup_environment() {
    print_info "Setting up environment configuration..."
    
    # Create .env file if it doesn't exist
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
    
    # Create necessary directories
    print_info "Creating necessary directories..."
    mkdir -p logs project_results emergency_backups
    
    print_success "Environment setup complete"
}

# ============================================
# NATIVE SETUP (Ubuntu/Debian)
# ============================================

native_check_system_debian() {
    print_info "Checking system compatibility (Ubuntu/Debian)..."
    
    if [[ ! -f /etc/debian_version ]]; then
        print_error "This path is for Ubuntu/Debian systems."
        return 1
    fi
    
    print_success "Running on Ubuntu/Debian system"
    return 0
}

native_install_python_debian() {
    print_info "Installing Python 3.12 (Ubuntu/Debian)..."
    
    # Check if Python 3.12 is already installed
    if command -v python3.12 &> /dev/null; then
        print_success "Python 3.12 is already installed"
        return
    fi
    
    # Add deadsnakes PPA
    print_info "Adding deadsnakes PPA..."
    sudo add-apt-repository ppa:deadsnakes/ppa -y
    
    # Update package list
    print_info "Updating package list..."
    sudo apt update
    
    # Install Python 3.12
    print_info "Installing Python 3.12..."
    sudo apt install -y python3.12 python3.12-venv python3.12-dev
    
    print_success "Python 3.12 installed successfully"
}

post_native_quickstart() {
    if [ -f "./quickstart.sh" ]; then
        print_info "Running quickstart to launch backend and frontend..."
        # Try with bash to avoid executable bit requirement
        bash ./quickstart.sh || ./quickstart.sh || true
    else
        print_warning "quickstart.sh not found; skipping auto-start."
    fi
}

native_setup_debian() {
    if ! native_check_system_debian; then
        return 1
    fi
    
    # Install system dependencies
    print_info "Installing system dependencies (Ubuntu/Debian)..."
    sudo apt update
    sudo apt install -y curl git build-essential screen
    
    native_install_python_debian
    native_install_pdm_uv
    native_install_node
    native_setup_environment
    native_setup_project
    native_install_frontend
    
    echo ""
    echo "========================================"
    print_success "Native Setup Complete!"
    echo "========================================"
    echo ""
    echo "To run the servers:"
    echo ""
    echo "1. Start the backend server:"
    echo "   screen -S backend_server"
    echo "   eval \"\$(pdm venv activate)\""
    echo "   python -m sentientresearchagent"
    echo "   # Press Ctrl+A, then D to detach"
    echo ""
    echo "2. Start the frontend server:"
    echo "   screen -S frontend_server"
    echo "   cd frontend && npm run dev"
    echo "   # Press Ctrl+A, then D to detach"
    echo ""
    echo "Server URLs:"
    echo "  - Backend API: http://localhost:5000"
    echo "  - Frontend: http://localhost:3000"
    echo ""
    echo "Screen commands:"
    echo "  - List screens: screen -ls"
    echo "  - Reattach: screen -r backend_server"
    echo "  - Kill screen: screen -X -S backend_server quit"
    echo ""
    print_warning "Don't forget to:"
    echo "  1. Update .env file with your API keys"
    echo "  2. Reload your shell to update PATH (e.g., 'source ~/.zshrc' or 'source ~/.bashrc')"
    echo ""
    
    # Auto-launch servers and open browser
    post_native_quickstart
}

# ============================================
# NATIVE SETUP (macOS)
# ============================================

native_check_system_macos() {
    print_info "Checking system compatibility (macOS)..."
    if [ "$(uname -s)" != "Darwin" ]; then
        print_error "This path is for macOS systems."
        return 1
    fi
    print_success "Running on macOS"
    return 0
}

native_install_homebrew() {
    if command -v brew &>/dev/null; then
        print_success "Homebrew is already installed"
        brew update || true
    else
        print_info "Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        # Initialize brew for current session and future shells
        if [ -x "/opt/homebrew/bin/brew" ]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
            append_to_profile_once 'eval "$(/opt/homebrew/bin/brew shellenv)"'
        elif [ -x "/usr/local/bin/brew" ]; then
            eval "$(/usr/local/bin/brew shellenv)"
            append_to_profile_once 'eval "$(/usr/local/bin/brew shellenv)"'
        fi
        print_success "Homebrew installed"
    fi
}

native_install_system_deps_macos() {
    print_info "Installing system dependencies (macOS)..."
    brew install git screen || true
}

native_install_python_macos() {
    print_info "Installing Python 3.12 (macOS)..."
    
    if command -v python3.12 &>/dev/null; then
        print_success "Python 3.12 is already installed"
        return
    fi
    
    native_install_homebrew
    
    # Install Python 3.12 via Homebrew (keg-only)
    brew install python@3.12
    
    # Ensure the python3.12 binary is on PATH
    PY312_BIN="$(brew --prefix)/opt/python@3.12/bin"
    if [ -x "$PY312_BIN/python3.12" ]; then
        export PATH="$PY312_BIN:$PATH"
        append_to_profile_once 'export PATH="'"$PY312_BIN"'":$PATH'
        print_success "Added Python 3.12 to PATH"
    else
        print_warning "Could not locate python3.12 in Homebrew prefix; you may need to restart your shell."
    fi
}

native_setup_macos() {
    if ! native_check_system_macos; then
        return 1
    fi
    
    native_install_homebrew
    native_install_system_deps_macos
    native_install_python_macos
    native_install_pdm_uv
    native_install_node
    native_setup_environment
    native_setup_project
    native_install_frontend
    
    echo ""
    echo "========================================"
    print_success "Native Setup Complete!"
    echo "========================================"
    echo ""
    echo "To run the servers:"
    echo ""
    echo "1. Start the backend server:"
    echo "   screen -S backend_server"
    echo "   eval \"\$(pdm venv activate)\""
    echo "   python -m sentientresearchagent"
    echo "   # Press Ctrl+A, then D to detach"
    echo ""
    echo "2. Start the frontend server:"
    echo "   screen -S frontend_server"
    echo "   cd frontend && npm run dev"
    echo "   # Press Ctrl+A, then D to detach"
    echo ""
    echo "Server URLs:"
    echo "  - Backend API: http://localhost:5000"
    echo "  - Frontend: http://localhost:3000"
    echo ""
    echo "Screen commands:"
    echo "  - List screens: screen -ls"
    echo "  - Reattach: screen -r backend_server"
    echo "  - Kill screen: screen -X -S backend_server quit"
    echo ""
    print_warning "Don't forget to:"
    echo "  1. Update .env file with your API keys"
    echo "  2. Reload your shell to update PATH (e.g., 'source ~/.zshrc' or 'source ~/.bashrc')"
    echo ""
    
    # Auto-launch servers and open browser
    post_native_quickstart
}

# ============================================
# NATIVE SETUP DISPATCH
# ============================================

native_setup() {
    detect_os
    case "$OS_FAMILY" in
        macos)
            print_info "Starting native macOS setup..."
            native_setup_macos
            ;;
        debian)
            print_info "Starting native Ubuntu/Debian setup..."
            native_setup_debian
            ;;
        *)
            print_error "Unsupported system detected. This script supports macOS and Ubuntu/Debian."
            echo "Please install dependencies manually (Python 3.12, PDM, UV, NVM/Node, npm) and rerun."
            return 1
            ;;
    esac
}

# ============================================
# MAIN MENU
# ============================================

show_menu() {
    echo ""
    echo "Choose your setup method:"
    echo ""
    echo "  1) Docker Setup (Recommended)"
    echo "     - Isolated environment"
    echo "     - No system dependencies"
    echo "     - One-command setup"
    echo "     - Best for production"
    echo ""
    echo "  2) Native Setup (macOS or Ubuntu/Debian)"
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
            docker_setup
            ;;
        2)
            native_setup
            ;;
        *)
            print_error "Invalid choice. Please run the script again and select 1 or 2."
            exit 1
            ;;
    esac
}

# ============================================
# MAIN EXECUTION
# ============================================

main() {
    show_banner
    
    # Handle command line arguments
    case "$1" in
        --docker)
            docker_setup
            ;;
        --native)
            native_setup
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --docker    Run Docker setup directly"
            echo "  --native    Run native setup (macOS or Ubuntu/Debian) directly"
            echo "  --help      Show this help message"
            echo ""
            echo "Without options, an interactive menu will be shown."
            ;;
        "")
            show_menu
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
}

# Error handling
trap 'print_error "Setup failed! Check the error messages above."; exit 1' ERR

# Run main function with all arguments
main "$@"