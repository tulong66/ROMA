# 🚀 Quick Start Guide

Get up and running with the Sentient Research Agent framework in 5 minutes.

## 📋 Prerequisites

- Python 3.12 or higher
- API key for LLM provider (OpenAI, Anthropic, or OpenRouter)

## ⚡ Installation

### Option 1: Clone and Install (Recommended for Development)

```bash
# Clone the repository
git clone https://github.com/your-org/SentientResearchAgent.git
cd SentientResearchAgent

# Install with PDM (recommended)
pip install pdm
pdm install

# Or install with pip
pip install -e .
```

### Option 2: Direct Installation (Coming Soon)

```bash
pip install sentient-research-agent
```

## 🔑 Setup API Keys

### Environment Variables (Recommended)

```bash
# For OpenAI
export OPENAI_API_KEY="your-openai-api-key"

# For Anthropic
export ANTHROPIC_API_KEY="your-anthropic-api-key"

# For OpenRouter (supports multiple models)
export OPENROUTER_API_KEY="your-openrouter-api-key"
```

### Configuration File

Create a `sentient.yaml` file in your project directory:

```yaml
llm:
  provider: "openrouter"  # or "openai", "anthropic"
  model: "openrouter/anthropic/claude-3-7-sonnet"
  api_key: "${OPENROUTER_API_KEY}"  # Uses environment variable
  temperature: 0.7

execution:
  max_concurrent_nodes: 3
  max_execution_steps: 100
  enable_hitl: false  # Set to true for human oversight

cache:
  enabled: true
  cache_type: "file"
  cache_dir: ".agent_cache"

logging:
  level: "INFO"
```

## 🎯 Your First Agent

### Simple Usage

```python
from sentientresearchagent import SimpleSentientAgent

# Create an agent (uses config from sentient.yaml or environment)
agent = SimpleSentientAgent.create()

# Execute a research task
result = agent.execute("Research the latest developments in quantum computing")

print("Status:", result['status'])
print("Output:", result['final_output'])
print("Time:", f"{result['execution_time']:.2f}s")
```

### With Custom Configuration

```python
from sentientresearchagent import SimpleSentientAgent

# Create agent with specific config file
agent = SimpleSentientAgent.create(config_path="my_custom_config.yaml")

# Execute with options
result = agent.execute(
    "Write a comprehensive report on renewable energy trends",
    max_steps=50
)

if result['status'] == 'completed':
    print(result['final_output'])
else:
    print("Error:", result.get('error'))
```

### Streaming Execution

```python
from sentientresearchagent import SimpleSentientAgent

agent = SimpleSentientAgent.create()

# Stream progress updates
for update in agent.stream_execution("Analyze the impact of AI on job markets"):
    print(f"[{update['status']}] {update['message']} ({update.get('progress', 0)}%)")
    
    if update['status'] == 'completed':
        print("\nFinal Output:")
        print(update['final_output'])
```

## 🎨 Examples by Use Case

### Research and Analysis

```python
# Market research
result = agent.execute("Research the electric vehicle market in Europe and identify key trends")

# Technical analysis  
result = agent.execute("Analyze the pros and cons of microservices architecture")

# Competitive analysis
result = agent.execute("Compare the features and pricing of top 3 CRM solutions")
```

### Content Creation

```python
# Blog post writing
result = agent.execute("Write a 1000-word blog post about sustainable fashion trends")

# Report generation
result = agent.execute("Create a quarterly business report based on Q3 2024 performance data")

# Documentation
result = agent.execute("Write API documentation for a REST service with CRUD operations")
```

### Data Analysis

```python
# Trend analysis
result = agent.execute("Analyze social media sentiment trends for electric vehicles over the past year")

# Comparative analysis
result = agent.execute("Compare the performance of different machine learning algorithms for image classification")
```

## 🔧 Understanding What's Happening

When you execute a goal, the framework uses sophisticated agents:

1. **Planning Agents** break down your goal into subtasks
2. **Execution Agents** perform specific tasks (search, analysis, writing)
3. **Aggregation Agents** combine results into the final output

### Behind the Scenes

```python
# Your simple call:
result = agent.execute("Research quantum computing")

# Internally, the framework:
# 1. CoreResearchPlanner creates a research strategy
# 2. SearchExecutor agents gather information
# 3. SearchSynthesizer agents process results
# 4. DefaultAggregator combines everything
# 5. Returns final comprehensive output
```

## 📊 Monitoring Progress

### Enable Detailed Logging

```python
import logging
logging.basicConfig(level=logging.INFO)

# Now you'll see detailed framework operations
result = agent.execute("Your goal here")
```

### Access Framework Details

```python
result = agent.execute("Research topic")

# Access detailed framework information
framework_details = result.get('framework_result', {})
print("Execution steps:", framework_details)
```

## 🎛️ Configuration Options

### Quick Configuration Tweaks

```python
# More detailed execution
agent = SimpleSentientAgent.create()
result = agent.execute("Complex research task", max_steps=150)

# With human oversight
# Set enable_hitl: true in your config, then:
result = agent.execute("Important business decision analysis")
# Framework will prompt for human input at key decision points
```

### Performance Tuning

```yaml
# In sentient.yaml
execution:
  max_concurrent_nodes: 5      # More parallel processing
  max_execution_steps: 200     # Allow longer execution
  
cache:
  enabled: true               # Cache results for faster re-runs
  ttl_seconds: 7200          # 2 hour cache
```

## 🔍 Troubleshooting Quick Fixes

### Common Issues

**"No API key found"**
```bash
# Make sure your API key is set
echo $OPENAI_API_KEY
# If empty, set it:
export OPENAI_API_KEY="your-key-here"
```

**"Configuration not found"**
```python
# Check current directory for sentient.yaml
import os
print("Current directory:", os.getcwd())
print("Config exists:", os.path.exists("sentient.yaml"))
```

**"Execution failed"**
```python
# Check the error details
result = agent.execute("your goal")
if result['status'] == 'failed':
    print("Error details:", result['error'])
```

### Getting Help

1. **Check logs**: Look in `current_run.log` for detailed error information
2. **Verify configuration**: Ensure your `sentient.yaml` is valid
3. **Test API keys**: Try a simple request to verify connectivity
4. **Review examples**: Check if your use case matches provided examples

## 🚀 Next Steps

Now that you have the basics working:

1. **Explore Examples**: Check out [EXAMPLES.md](EXAMPLES.md) for more use cases
2. **Understand the Architecture**: Read [ARCHITECTURE.md](ARCHITECTURE.md) to see how it works
3. **Custom Configuration**: Learn more in [CONFIGURATION.md](CONFIGURATION.md)
4. **Build Custom Agents**: See [CUSTOM_AGENTS.md](CUSTOM_AGENTS.md) for extending the framework

## 💡 Tips for Success

1. **Be Specific**: More specific goals lead to better results
2. **Use Streaming**: For long tasks, use `stream_execution()` to monitor progress
3. **Enable Caching**: Speeds up similar tasks significantly
4. **Start Simple**: Begin with basic tasks and gradually increase complexity
5. **Monitor Logs**: Keep an eye on logs to understand what's happening

Ready to build something amazing? Let's go! 🚀 