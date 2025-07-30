#!/bin/bash

# SentientResearchAgent Native Ubuntu Setup Script
# This script sets up the development environment on Ubuntu/Debian systems

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
                                        
 Research Agent - Native Ubuntu Setup
EOF

echo ""
print_info "Starting SentientResearchAgent native setup for Ubuntu/Debian..."
echo ""

# Check if running on Ubuntu/Debian
check_system() {
    print_info "Checking system compatibility..."
    
    if [[ ! -f /etc/debian_version ]]; then
        print_error "This script is designed for Ubuntu/Debian systems."
        print_error "For other systems, please install dependencies manually."
        exit 1
    fi
    
    print_success "Running on Ubuntu/Debian system"
}

# Install Python 3.12
install_python() {
    print_info "Installing Python 3.12..."
    
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

# Install PDM and UV
install_pdm_uv() {
    print_info "Installing PDM and UV package managers..."
    
    # Install PDM
    if ! command -v pdm &> /dev/null; then
        print_info "Installing PDM..."
        curl -sSL https://pdm-project.org/install-pdm.py | python3 -
        
        # Add PDM to PATH
        export PATH="$HOME/.local/bin:$PATH"
        
        # Add to bashrc if not already there
        if ! grep -q "export PATH=\"\$HOME/.local/bin:\$PATH\"" ~/.bashrc; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
        fi
    else
        print_success "PDM is already installed"
    fi
    
    # Install UV
    if ! command -v uv &> /dev/null; then
        print_info "Installing UV..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        
        # Source cargo env for UV
        source "$HOME/.cargo/env"
        
        # Add to bashrc if not already there
        if ! grep -q "source \"\$HOME/.cargo/env\"" ~/.bashrc; then
            echo 'source "$HOME/.cargo/env"' >> ~/.bashrc
        fi
    else
        print_success "UV is already installed"
    fi
    
    print_success "PDM and UV installed successfully"
}

# Install NVM and Node.js
install_node() {
    print_info "Installing NVM and Node.js..."
    
    # Install NVM
    if [ ! -d "$HOME/.nvm" ]; then
        print_info "Installing NVM..."
        curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
        
        # Load NVM
        export NVM_DIR="$HOME/.nvm"
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    else
        print_success "NVM is already installed"
        # Load NVM
        export NVM_DIR="$HOME/.nvm"
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    fi
    
    # Install Node.js 23.11.0
    print_info "Installing Node.js v23.11.0..."
    nvm install 23.11.0
    nvm use 23.11.0
    
    # Install specific npm version
    print_info "Installing npm v10.9.2..."
    npm install -g npm@10.9.2
    
    # Verify versions
    NODE_VERSION=$(node -v)
    NPM_VERSION=$(npm -v)
    
    if [[ "$NODE_VERSION" == "v23.11.0" ]] && [[ "$NPM_VERSION" == "10.9.2" ]]; then
        print_success "Node.js $NODE_VERSION and npm $NPM_VERSION installed successfully"
    else
        print_warning "Version mismatch - Node: $NODE_VERSION (expected v23.11.0), npm: $NPM_VERSION (expected 10.9.2)"
    fi
}

# Setup project with PDM
setup_project() {
    print_info "Setting up project with PDM..."
    
    # Check if we're in the project directory
    if [ ! -f "pyproject.toml" ]; then
        print_error "Please run this script from the SentientResearchAgent project root directory"
        exit 1
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

# Install frontend dependencies
install_frontend() {
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

# Setup environment configuration
setup_environment() {
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

# Display final instructions
display_instructions() {
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
    echo "  - Frontend: http://localhost:5173"
    echo ""
    echo "Screen commands:"
    echo "  - List screens: screen -ls"
    echo "  - Reattach: screen -r backend_server"
    echo "  - Kill screen: screen -X -S backend_server quit"
    echo ""
    print_warning "Don't forget to:"
    echo "  1. Update .env file with your API keys"
    echo "  2. Source ~/.bashrc to update PATH:"
    echo "     source ~/.bashrc"
    echo ""
}

# Main execution
main() {
    check_system
    
    # Install system dependencies
    print_info "Installing system dependencies..."
    sudo apt update
    sudo apt install -y curl git build-essential screen
    
    install_python
    install_pdm_uv
    install_node
    setup_environment
    setup_project
    install_frontend
    display_instructions
}

# Error handling
trap 'print_error "Setup failed! Check the error messages above."; exit 1' ERR

# Run main function
main