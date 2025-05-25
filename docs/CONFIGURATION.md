# ⚙️ Configuration Guide

Complete guide to configuring the Sentient Research Agent framework.

## 📋 Configuration Overview

The framework uses a layered configuration system that balances ease of use with sophisticated control:

1. **Environment Variables** - For API keys and basic settings
2. **YAML Configuration Files** - For detailed framework configuration
3. **Programmatic Configuration** - For dynamic setups
4. **Agent-Specific Configuration** - Built into the sophisticated agent system

## 🔧 Basic Configuration

### Environment Variables

Set these environment variables for quick setup:

```bash
# LLM Provider API Keys
export OPENAI_API_KEY="your-openai-key"
export ANTHROPIC_API_KEY="your-anthropic-key" 
export OPENROUTER_API_KEY="your-openrouter-key"

# Basic Framework Settings
export SENTIENT_ENV="production"          # or "development", "testing"
export SENTIENT_LLM_PROVIDER="openrouter"
export SENTIENT_LLM_MODEL="openrouter/anthropic/claude-3-7-sonnet"
export SENTIENT_LOG_LEVEL="INFO"
export SENTIENT_CACHE_ENABLED="true"
```

### Quick YAML Configuration

Create `sentient.yaml` in your project root:

```yaml
# Minimal working configuration
llm:
  provider: "openrouter"
  model: "openrouter/anthropic/claude-3-7-sonnet" 
  api_key: "${OPENROUTER_API_KEY}"

# Optional: Basic execution settings
execution:
  max_execution_steps: 100
  enable_hitl: false
```

## 🏗️ Complete Configuration Reference

### LLM Configuration

```yaml
llm:
  provider: "openrouter"                    # "openai", "anthropic", "openrouter", "azure"
  model: "openrouter/anthropic/claude-3-7-sonnet"
  api_key: "${OPENROUTER_API_KEY}"         # Use environment variable
  api_base: null                           # Custom API endpoint (optional)
  temperature: 0.7                         # 0.0-2.0, controls randomness
  max_tokens: 4000                         # Maximum response length
  timeout: 60.0                            # Request timeout in seconds
  max_retries: 3                           # Retry failed requests
```

#### Supported Providers and Models

**OpenRouter (Recommended - Access to Multiple Models)**
```yaml
llm:
  provider: "openrouter"
  model: "openrouter/anthropic/claude-3-7-sonnet"    # High quality reasoning
  # model: "openrouter/anthropic/claude-3-haiku"     # Fast and efficient
  # model: "openrouter/openai/gpt-4"                 # OpenAI GPT-4
  # model: "openrouter/meta-llama/llama-3-70b"       # Open source option
```

**OpenAI Direct**
```yaml
llm:
  provider: "openai"
  model: "gpt-4"                          # or "gpt-4-turbo", "gpt-3.5-turbo"
  api_key: "${OPENAI_API_KEY}"
```

**Anthropic Direct**
```yaml
llm:
  provider: "anthropic"
  model: "claude-3-sonnet-20240229"       # or "claude-3-haiku-20240307"
  api_key: "${ANTHROPIC_API_KEY}"
```

### Execution Configuration

```yaml
execution:
  max_concurrent_nodes: 3                  # Number of parallel tasks (1-10)
  max_execution_steps: 100                 # Maximum total execution steps
  max_retries: 3                          # Task retry attempts
  retry_delay_seconds: 2.0                # Delay between retries
  rate_limit_rpm: 60                      # Requests per minute limit
  enable_hitl: false                      # Human-in-the-loop oversight
  hitl_timeout_seconds: 300.0             # HITL response timeout (5 min)
```

#### Execution Settings Explained

- **max_concurrent_nodes**: How many tasks can run simultaneously
  - `1`: Sequential execution (safest for API limits)
  - `2-3`: Good balance of speed and stability
  - `4+`: Faster but may hit rate limits

- **max_execution_steps**: Total steps before stopping
  - `25-50`: Simple tasks
  - `50-100`: Standard complex tasks
  - `100+`: Very complex research or writing

- **enable_hitl**: Human oversight
  - `false`: Fully autonomous (default)
  - `true`: Requests human input for critical decisions

### Cache Configuration

```yaml
cache:
  enabled: true                           # Enable/disable caching
  cache_type: "file"                      # "memory", "file", "redis"
  cache_dir: ".agent_cache"               # Directory for file cache
  ttl_seconds: 3600                       # Time-to-live (1 hour)
  max_size: 1000                          # Maximum cache entries
  redis_url: null                         # Redis connection (if using Redis)
```

#### Cache Types

**File Cache (Recommended)**
```yaml
cache:
  cache_type: "file"
  cache_dir: ".agent_cache"               # Persists between sessions
  ttl_seconds: 7200                       # 2 hours for research tasks
```

**Memory Cache (Fastest)**
```yaml
cache:
  cache_type: "memory"                    # Lost when process ends
  max_size: 500                          # Entries in memory
  ttl_seconds: 1800                      # 30 minutes
```

**Redis Cache (Distributed)**
```yaml
cache:
  cache_type: "redis"
  redis_url: "redis://localhost:6379"    # Redis server
  ttl_seconds: 86400                     # 24 hours
```

### Logging Configuration

```yaml
logging:
  level: "INFO"                          # "DEBUG", "INFO", "WARNING", "ERROR"
  enable_console: true                   # Console output
  enable_file: true                      # File logging
  file_path: "sentient_agent.log"        # Log file location
  file_rotation: "1 day"                 # Rotate daily
  file_retention: "1 week"               # Keep for 1 week
  format: "<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
```

## 🤖 Agent Configuration (Advanced)

The framework includes sophisticated pre-configured agents. You can reference them by name:

### Available Agent Names

```yaml
# These agents are pre-configured and available by name:
agents:
  planners:
    - "default_planner"           # SimpleTestPlanner for general use
    - "CoreResearchPlanner"       # Advanced research planning
  
  executors:
    - "SearchExecutor"            # Web search strategy
    - "SearchSynthesizer"         # Search result synthesis  
    - "BasicReportWriter"         # Content writing
    - "OpenAICustomSearcher"      # Direct search integration
  
  aggregators:
    - "default_aggregator"        # Result combination
  
  specialists:
    - "default_atomizer"          # Task granularity optimization
    - "PlanModifier"              # Plan modification and HITL
```

### Using Specific Agents

```python
# In your code, you can specify agent preferences
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode

# Create a task node with specific agent preference
node = TaskNode(
    goal="Research quantum computing",
    task_type=TaskType.SEARCH,
    node_type=NodeType.PLAN,
    agent_name="CoreResearchPlanner"  # Use specific sophisticated planner
)
```

## 🌍 Environment-Specific Configuration

### Development Environment

```yaml
# sentient.development.yaml
llm:
  provider: "openrouter"
  model: "openrouter/anthropic/claude-3-haiku"  # Faster/cheaper for dev
  temperature: 0.5

execution:
  max_execution_steps: 25                       # Faster iterations
  enable_hitl: true                            # More oversight in development

logging:
  level: "DEBUG"                               # Detailed logging
  enable_console: true

cache:
  enabled: true
  ttl_seconds: 1800                            # 30 minutes for dev

environment: "development"
```

### Production Environment

```yaml
# sentient.production.yaml
llm:
  provider: "openrouter"
  model: "openrouter/anthropic/claude-3-7-sonnet"  # High quality
  temperature: 0.7

execution:
  max_execution_steps: 100
  max_concurrent_nodes: 3
  enable_hitl: false                           # Autonomous operation

logging:
  level: "INFO"                                # Clean logs
  enable_file: true
  file_rotation: "1 day"

cache:
  enabled: true
  cache_type: "file"
  ttl_seconds: 7200                            # 2 hours

environment: "production"
```

### Testing Environment

```yaml
# sentient.testing.yaml
llm:
  provider: "openrouter"
  model: "openrouter/anthropic/claude-3-haiku"  # Fast for tests
  temperature: 0.0                              # Deterministic

execution:
  max_execution_steps: 10                       # Quick tests
  max_concurrent_nodes: 1                       # Predictable execution

logging:
  level: "WARNING"                              # Minimal noise
  enable_console: false
  enable_file: false

cache:
  enabled: false                                # Fresh execution each test

environment: "testing"
```

## 📁 Configuration File Loading

The framework tries these locations in order:

1. Explicitly provided config file
2. `sentient.{environment}.yaml` (e.g., `sentient.development.yaml`)
3. `config/sentient.{environment}.yaml`
4. `sentient.yaml` (default)
5. `config/sentient.yaml`
6. `.sentient.yaml` (hidden file)
7. Environment variables
8. Built-in defaults

### Loading Examples

```python
from sentientresearchagent import SimpleSentientAgent

# Auto-load (tries locations above)
agent = SimpleSentientAgent.create()

# Specific config file
agent = SimpleSentientAgent.create(config_path="my_config.yaml")

# Environment-specific
import os
os.environ["SENTIENT_ENV"] = "development"
agent = SimpleSentientAgent.create()  # Loads sentient.development.yaml
```

## 🔧 Programmatic Configuration

For dynamic configurations:

```python
from sentientresearchagent.config import SentientConfig, LLMConfig, ExecutionConfig

# Create configuration programmatically
config = SentientConfig(
    llm=LLMConfig(
        provider="openrouter",
        model="openrouter/anthropic/claude-3-7-sonnet",
        api_key=os.getenv("OPENROUTER_API_KEY"),
        temperature=0.7
    ),
    execution=ExecutionConfig(
        max_execution_steps=150,
        max_concurrent_nodes=2,
        enable_hitl=False
    )
)

# Use with agent
agent = SimpleSentientAgent(config=config)
```

## 🔍 Configuration Validation

### Validate Your Configuration

```python
from sentientresearchagent.config import load_config

# Load and validate
config = load_config()

# Check for issues
validation_issues = config.validate_api_keys()
if validation_issues:
    print("Configuration issues:", validation_issues)
else:
    print("Configuration is valid!")
```

### Common Configuration Issues

**Missing API Keys**
```yaml
# ❌ Wrong - API key not found
llm:
  provider: "openai"
  api_key: "your-api-key-here"

# ✅ Correct - Use environment variable
llm:
  provider: "openai"
  api_key: "${OPENAI_API_KEY}"
```

**Invalid Model Names**
```yaml
# ❌ Wrong - Invalid model
llm:
  provider: "openrouter"
  model: "gpt-4"  # Should include provider prefix

# ✅ Correct - Full model path
llm:
  provider: "openrouter"
  model: "openrouter/openai/gpt-4"
```

**Resource Limits**
```yaml
# ⚠️ Caution - May hit rate limits
execution:
  max_concurrent_nodes: 10        # Very high
  max_execution_steps: 500        # Very long

# ✅ Better - Balanced settings
execution:
  max_concurrent_nodes: 3         # Reasonable parallelism
  max_execution_steps: 100        # Sufficient for most tasks
```

## 🎯 Configuration Best Practices

### 1. Use Environment Variables for Secrets

```bash
# Never commit API keys to version control
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
```

### 2. Environment-Specific Configs 

project/
├── sentient.yaml # Default/base config
├── sentient.development.yaml # Development overrides
├── sentient.production.yaml # Production settings
└── sentient.testing.yaml # Test settings


### 3. Start Conservative

```yaml
# Start with safe settings, then optimize
execution:
  max_concurrent_nodes: 2         # Start low
  max_execution_steps: 50         # Reasonable limit
  
cache:
  enabled: true                   # Always enable caching
  ttl_seconds: 3600              # 1 hour is usually good
```

### 4. Monitor and Adjust

```yaml
logging:
  level: "INFO"                   # Watch for performance issues
  enable_file: true              # Keep logs for analysis
```

## 🚨 Troubleshooting Configuration

### Quick Diagnostics

```python
from sentientresearchagent.config import load_config
import os

# Check environment
print("Environment:", os.getenv("SENTIENT_ENV", "not set"))
print("Config file exists:", os.path.exists("sentient.yaml"))

# Test config loading
try:
    config = load_config()
    print("✅ Configuration loaded successfully")
    print("Provider:", config.llm.provider)
    print("Model:", config.llm.model)
except Exception as e:
    print("❌ Configuration error:", e)
```

### Common Solutions

1. **"Configuration not found"** → Create `sentient.yaml` in project root
2. **"Invalid API key"** → Check environment variable is set
3. **"Model not available"** → Verify model name and provider
4. **"Rate limit exceeded"** → Reduce `max_concurrent_nodes`
5. **"Timeout errors"** → Increase `timeout` in LLM config

This configuration system provides maximum flexibility while maintaining the sophisticated agent system that's already built into the framework.