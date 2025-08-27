# 🤝 Contributing to SentientResearchAgent

First off, thank you for considering contributing to SentientResearchAgent! It's people like you that make SentientResearchAgent such a great tool. We welcome contributions from everyone, regardless of their experience level.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [How Can I Contribute?](#how-can-i-contribute)
- [Development Setup](#development-setup)
- [Style Guidelines](#style-guidelines)
- [Commit Guidelines](#commit-guidelines)
- [Pull Request Process](#pull-request-process)
- [Community](#community)

## Code of Conduct

This project and everyone participating in it is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to [salaheddin@sentient.xyz](mailto:salaheddin@sentient.xyz).

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally
3. **Create a branch** for your contribution
4. **Make your changes** and test them
5. **Push to your fork** and submit a pull request

## How Can I Contribute?

### 🐛 Reporting Bugs

Before creating bug reports, please check existing issues to avoid duplicates. When creating a bug report, please include:

- A clear and descriptive title
- Steps to reproduce the issue
- Expected behavior vs actual behavior
- Screenshots if applicable
- Your environment details (OS, Python version, etc.)

**Use the bug report template** when creating a new issue.

### 💡 Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion, please include:

- A clear and descriptive title
- A detailed description of the proposed feature
- Why this enhancement would be useful
- Possible implementation approaches

### 🧩 Contributing Agent Templates

We love new agent templates! To contribute one:

1. Create your agent in `src/sentientresearchagent/agent_templates/`
2. Add documentation in `docs/agents/`
3. Include example usage in `examples/`
4. Add tests in `tests/agents/`

### 📝 Improving Documentation

Documentation improvements are always welcome! This includes:

- Fixing typos or clarifying existing docs
- Adding examples and use cases
- Translating documentation
- Improving code comments

## Development Setup

### Prerequisites

- Python 3.12+
- Node.js 18+
- PDM (Python Dependency Manager)
- Git

### Setting Up Your Development Environment

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/SentientResearchAgent.git
cd SentientResearchAgent

# Add upstream remote
git remote add upstream https://github.com/salzubi401/SentientResearchAgent.git

# Install Python dependencies
pdm install --dev

# Install frontend dependencies
cd frontend
npm install
cd ..

# Set up pre-commit hooks
pdm run pre-commit install

# Create a feature branch
git checkout -b feature/your-feature-name
```

### Running Tests

```bash
# Run all tests
pdm run pytest

# Run specific test file
pdm run pytest tests/test_specific.py

# Run with coverage
pdm run pytest --cov=sentientresearchagent

# Run linting
pdm run ruff check .
pdm run mypy .
```

### Running the Development Server

```bash
# Start backend
pdm run python -m sentientresearchagent --debug

# In another terminal, start frontend
cd frontend
npm run dev
```

## Style Guidelines

### Python Style Guide

We follow [PEP 8](https://pep8.org/) with these additions:

- Line length: 100 characters
- Use type hints for all functions
- Docstrings for all public functions (Google style)
- Sort imports with `isort`

Example:
```python
from typing import Optional, List

def process_task(
    task_name: str,
    options: Optional[List[str]] = None
) -> dict:
    """Process a task with given options.
    
    Args:
        task_name: Name of the task to process
        options: Optional list of processing options
        
    Returns:
        Dictionary containing processing results
    """
    # Implementation here
    pass
```

### TypeScript/React Style Guide

- Use functional components with hooks
- Use TypeScript for all new code
- Follow [Airbnb React Style Guide](https://airbnb.io/javascript/react/)

### Documentation Style

- Use clear, concise language
- Include code examples where helpful
- Keep paragraphs short
- Use active voice

## Commit Guidelines

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code changes that neither fix bugs nor add features
- `perf`: Performance improvements
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

### Examples

```bash
feat(agents): add podcast generator agent template

fix(hitl): resolve timeout issue in human intervention

docs(api): update agent creation examples

chore(deps): update litellm to v1.72.6
```

## Pull Request Process

1. **Ensure your code follows the style guidelines**
2. **Update documentation** if you're changing functionality
3. **Add tests** for new features
4. **Ensure all tests pass** locally
5. **Update the CHANGELOG.md** with your changes
6. **Create a pull request** with a clear title and description

### PR Template

When creating a PR, please use our template which includes:

- [ ] Description of changes
- [ ] Type of change (bug fix, feature, etc.)
- [ ] Testing performed
- [ ] Checklist of requirements

### Review Process

1. A maintainer will review your PR within 3 business days
2. Address any requested changes
3. Once approved, your PR will be merged

## Project Structure

```
SentientResearchAgent/
├── src/                    # Source code
│   └── sentientresearchagent/
│       ├── core/          # Core framework
│       ├── agents/        # Agent implementations
│       └── utils/         # Utilities
├── frontend/              # React frontend
├── tests/                 # Test suite
├── docs/                  # Documentation
├── examples/              # Example scripts
└── experiments/           # Experiment results
```

## Testing Philosophy

- Write tests for all new features
- Maintain test coverage above 80%
- Use meaningful test names
- Test edge cases and error conditions

## Community

- 💬 [Discord](https://discord.gg/sentientagent) - Get help and discuss features
- 🐛 [Issue Tracker](https://github.com/salzubi401/SentientResearchAgent/issues) - Report bugs
- 💡 [Discussions](https://github.com/salzubi401/SentientResearchAgent/discussions) - Share ideas

## Recognition

Contributors will be recognized in:

- The README contributors section
- Release notes
- Our website (coming soon)

## Questions?

Feel free to:
- Open an issue for questions
- Join our Discord community
- Email the maintainers

Thank you for contributing to SentientResearchAgent! 🚀