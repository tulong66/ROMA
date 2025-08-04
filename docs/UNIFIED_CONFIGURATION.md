# Unified Configuration System for SentientResearchAgent

## Current Configuration Challenges

1. **Multiple Configuration Sources**
   - Environment variables
   - sentient.yaml file
   - Profile YAML files
   - Programmatic overrides
   - Execution-time overrides

2. **Configuration Precedence Issues**
   - Unclear which source takes priority
   - Overrides don't always propagate to all components
   - Different components may have different views of configuration

3. **Component Synchronization**
   - NodeProcessor, ExecutionEngine, and SystemManager may have different configs
   - Handler contexts need manual updates
   - Profile initialization can reset configurations

## Recommended Best Practices

### 1. Single Source of Truth Pattern

```python
from sentientresearchagent.framework_entry import LightweightSentientAgent
from sentientresearchagent.config import load_config

# Load config once and modify it
config = load_config(config_file="sentient.yaml")

# Apply all your overrides to the config object
config.execution.skip_atomization = True
config.execution.max_recursion_depth = 1
config.execution.max_concurrent_nodes = 5
config.execution.enable_hitl = False

# Create agent with the modified config
agent = LightweightSentientAgent.create_with_profile(
    profile_name="crypto_analytics_agent",
    # Pass config overrides that will be applied during creation
    skip_atomization=True,
    max_recursion_depth=1
)

# Execute without additional overrides
result = await agent.execute(
    goal='your goal here',
    max_steps=50
)
```

### 2. Configuration at Creation Time (Recommended)

```python
# Pass all configuration when creating the agent
agent = LightweightSentientAgent.create_with_profile(
    profile_name="crypto_analytics_agent",
    skip_atomization=True,
    max_recursion_depth=1,
    max_concurrent_nodes=5,
    enable_hitl=False
)

# Execute with minimal parameters
result = await agent.execute(
    goal='your goal here',
    max_steps=50
)
```

### 3. Using Existing SystemManager (For Advanced Users)

```python
from sentientresearchagent.core.system_manager import SystemManagerV2
from sentientresearchagent.config import load_config

# Create and configure system manager once
config = load_config(config_file="sentient.yaml")
config.execution.skip_atomization = True
config.execution.max_recursion_depth = 1

system_manager = SystemManagerV2(config)

# Create agent with existing system manager
agent = LightweightSentientAgent.create_with_profile(
    profile_name="crypto_analytics_agent",
    system_manager=system_manager  # Use existing manager
)
```

## Configuration Hierarchy

1. **Default Values** (lowest priority)
   - Hardcoded in config classes

2. **Environment Variables**
   - SENTIENT_EXECUTION_SKIP_ATOMIZATION=true
   - SENTIENT_EXECUTION_MAX_RECURSION_DEPTH=1

3. **Configuration File (sentient.yaml)**
   ```yaml
   execution:
     skip_atomization: true
     max_recursion_depth: 1
   ```

4. **Profile Configuration**
   - Profile-specific settings from profile YAML files

5. **Programmatic Overrides** (highest priority)
   - Parameters passed to create_with_profile()
   - Parameters passed to execute()

## Common Issues and Solutions

### Issue: Configuration not being respected
**Solution**: Ensure you're applying configuration at creation time, not just execution time.

### Issue: Different components have different configs
**Solution**: Use the single source of truth pattern and create agent with all overrides.

### Issue: Profile initialization resets config
**Solution**: Pass system_manager parameter to create_with_profile() to reuse existing configuration.

## Future Improvements

1. **Centralized Configuration Manager**
   - Single component responsible for all configuration
   - Automatic propagation to all components
   - Configuration validation and type checking

2. **Configuration Immutability**
   - Once agent is created, configuration becomes read-only
   - All overrides must be applied at creation time

3. **Configuration Profiles**
   - Predefined configuration sets for common use cases
   - Easy switching between profiles

4. **Configuration API**
   ```python
   agent = LightweightSentientAgent.with_config({
       "profile": "crypto_analytics_agent",
       "execution": {
           "skip_atomization": True,
           "max_recursion_depth": 1
       }
   })
   ```