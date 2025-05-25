"""
Default configurations for the Sentient Research Agent framework.

This module provides sensible defaults that work out of the box for most users,
while still allowing full customization when needed.
"""

from typing import Dict, Any
from ..hierarchical_agent_framework.types import TaskType

# Default LLM configuration - optimized for cost and performance
DEFAULT_LLM_CONFIG = {
    "provider": "openai",
    "model": "gpt-4o-mini",  # More cost-effective than gpt-4
    "temperature": 0.7,
    "max_tokens": 2000,      # Reasonable default
    "timeout": 30.0,
    "max_retries": 3
}

# Conservative execution defaults for reliability
DEFAULT_EXECUTION_CONFIG = {
    "max_concurrent_nodes": 2,    # Conservative for API rate limits
    "max_retries": 3,
    "retry_delay_seconds": 2.0,
    "rate_limit_rpm": 30,         # Conservative rate limiting
    "max_execution_steps": 50,    # Reasonable for most tasks
    "enable_hitl": False,         # Disabled by default for automation
    "hitl_timeout_seconds": 300.0
}

# Efficient caching defaults
DEFAULT_CACHE_CONFIG = {
    "enabled": True,
    "ttl_seconds": 3600,          # 1 hour - good balance
    "max_size": 500,              # Reasonable memory usage
    "cache_type": "memory",       # Simple default
    "cache_dir": ".agent_cache"
}

# User-friendly logging defaults
DEFAULT_LOGGING_CONFIG = {
    "level": "INFO",              # Not too verbose by default
    "enable_console": True,
    "enable_file": True,
    "file_path": "sentient_agent.log",
    "file_rotation": "1 day",
    "file_retention": "1 week"
}

# Default agent configurations for common use cases
DEFAULT_AGENT_CONFIGS = {
    "research_assistant": {
        "name": "research_assistant",
        "agent_type": "executor",
        "model_override": "gpt-4o-mini",
        "temperature_override": 0.3,  # More focused for research
        "system_prompt": """You are a research assistant specialized in finding and synthesizing information from multiple sources. 
        Focus on accuracy, cite sources when possible, and provide well-structured summaries.""",
        "supported_task_types": [TaskType.SEARCH.value, TaskType.THINK.value],
        "tools": ["web_search", "document_reader"],
        "enabled": True
    },
    
    "content_writer": {
        "name": "content_writer", 
        "agent_type": "executor",
        "model_override": "gpt-4o-mini",
        "temperature_override": 0.8,  # More creative for writing
        "system_prompt": """You are a skilled content writer who creates engaging, well-structured content.
        Focus on clarity, readability, and adapting tone to the target audience.""",
        "supported_task_types": [TaskType.WRITE.value],
        "tools": ["grammar_check", "style_guide"],
        "enabled": True
    },
    
    "data_analyst": {
        "name": "data_analyst",
        "agent_type": "executor", 
        "model_override": "gpt-4o-mini",
        "temperature_override": 0.2,  # Very focused for analysis
        "system_prompt": """You are a data analyst who excels at interpreting data, identifying trends, 
        and creating actionable insights. Always support conclusions with evidence.""",
        "supported_task_types": [TaskType.THINK.value, TaskType.AGGREGATE.value],
        "tools": ["data_processor", "chart_generator"],
        "enabled": True
    }
}

# Complete default configuration
DEFAULT_CONFIG = {
    "llm": DEFAULT_LLM_CONFIG,
    "cache": DEFAULT_CACHE_CONFIG,
    "execution": DEFAULT_EXECUTION_CONFIG,
    "logging": DEFAULT_LOGGING_CONFIG,
    "agents": DEFAULT_AGENT_CONFIGS,
    "config_version": "1.0.0",
    "environment": "production"
}

# Environment-specific overrides
DEVELOPMENT_OVERRIDES = {
    "logging": {
        "level": "DEBUG",
        "enable_console": True
    },
    "execution": {
        "max_execution_steps": 20,  # Faster iterations
        "enable_hitl": True         # More oversight in dev
    },
    "environment": "development"
}

TESTING_OVERRIDES = {
    "llm": {
        "model": "gpt-3.5-turbo",   # Faster/cheaper for tests
        "temperature": 0.0          # Deterministic
    },
    "cache": {
        "enabled": False            # Fresh execution each test
    },
    "execution": {
        "max_execution_steps": 10,  # Quick tests
        "max_concurrent_nodes": 1   # Simpler for testing
    },
    "logging": {
        "level": "WARNING",         # Less noise in tests
        "enable_file": False
    },
    "environment": "testing"
}

def get_default_config(environment: str = "production") -> Dict[str, Any]:
    """
    Get default configuration for the specified environment.
    
    Args:
        environment: Environment name ('production', 'development', 'testing')
        
    Returns:
        Default configuration dictionary
    """
    config = DEFAULT_CONFIG.copy()
    
    if environment == "development":
        config = deep_merge_dict(config, DEVELOPMENT_OVERRIDES)
    elif environment == "testing":
        config = deep_merge_dict(config, TESTING_OVERRIDES)
    
    return config

def deep_merge_dict(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge two dictionaries, with override taking precedence.
    
    Args:
        base: Base dictionary
        override: Override dictionary
        
    Returns:
        Merged dictionary
    """
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dict(result[key], value)
        else:
            result[key] = value
    
    return result

def create_minimal_config() -> Dict[str, Any]:
    """
    Create a minimal configuration with just the essentials.
    
    Returns:
        Minimal configuration dictionary
    """
    return {
        "llm": {
            "provider": "openai",
            "model": "gpt-4o-mini"
        },
        "execution": {
            "max_execution_steps": 25
        }
    }

def create_research_optimized_config() -> Dict[str, Any]:
    """
    Create a configuration optimized for research tasks.
    
    Returns:
        Research-optimized configuration
    """
    config = get_default_config()
    
    # Research-specific overrides
    research_overrides = {
        "llm": {
            "model": "gpt-4",           # Better reasoning for research
            "temperature": 0.3          # More focused
        },
        "execution": {
            "max_execution_steps": 100, # More thorough research
            "max_concurrent_nodes": 3    # Parallel research streams
        },
        "cache": {
            "ttl_seconds": 7200         # Longer cache for research data
        }
    }
    
    return deep_merge_dict(config, research_overrides)

def create_writing_optimized_config() -> Dict[str, Any]:
    """
    Create a configuration optimized for content writing tasks.
    
    Returns:
        Writing-optimized configuration
    """
    config = get_default_config()
    
    writing_overrides = {
        "llm": {
            "model": "gpt-4",
            "temperature": 0.8,         # More creative
            "max_tokens": 4000          # Longer content
        },
        "execution": {
            "max_execution_steps": 75,
            "enable_hitl": True         # Human review for content
        }
    }
    
    return deep_merge_dict(config, writing_overrides) 