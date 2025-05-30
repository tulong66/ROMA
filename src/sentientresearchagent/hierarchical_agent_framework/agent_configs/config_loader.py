"""
Agent Configuration Loader

Loads agent configurations from YAML files and resolves prompt references.
"""

import os
import importlib
from pathlib import Path
from typing import Dict, List, Any, Optional
from loguru import logger

try:
    from omegaconf import OmegaConf, DictConfig
except ImportError:
    logger.error("OmegaConf not installed. Please install with: pip install omegaconf>=2.3.0")
    raise


class AgentConfigLoader:
    """Loads and validates agent configurations from YAML files."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize the config loader.
        
        Args:
            config_dir: Directory containing agent configuration files.
                       If None, uses the directory containing this file.
        """
        if config_dir is None:
            config_dir = Path(__file__).parent
        
        self.config_dir = Path(config_dir)
        self.agents_config_file = self.config_dir / "agents.yaml"
        
        # Validate config directory exists
        if not self.config_dir.exists():
            raise FileNotFoundError(f"Config directory not found: {self.config_dir}")
        
        if not self.agents_config_file.exists():
            raise FileNotFoundError(f"Agents config file not found: {self.agents_config_file}")
    
    def load_config(self) -> DictConfig:
        """
        Load the agent configuration from YAML.
        
        Returns:
            OmegaConf DictConfig containing the agent configuration
        """
        try:
            logger.info(f"Loading agent configuration from: {self.agents_config_file}")
            config = OmegaConf.load(self.agents_config_file)
            
            # Validate basic structure
            if "agents" not in config:
                raise ValueError("Configuration must contain 'agents' section")
            
            logger.info(f"Loaded configuration for {len(config.agents)} agents")
            return config
            
        except Exception as e:
            logger.error(f"Failed to load agent configuration: {e}")
            raise
    
    def resolve_prompt(self, prompt_source: str) -> str:
        """
        Resolve a prompt reference to the actual prompt string.
        
        Args:
            prompt_source: Dot-notation path to the prompt (e.g., "prompts.planner_prompts.PLANNER_SYSTEM_MESSAGE")
        
        Returns:
            The resolved prompt string
        """
        try:
            # Split the prompt source into module and attribute
            parts = prompt_source.split('.')
            if len(parts) < 2:
                raise ValueError(f"Invalid prompt source format: {prompt_source}")
            
            # Import the module relative to the agent_configs package
            module_path = '.'.join(parts[:-1])
            attribute_name = parts[-1]
            
            # Import relative to this package
            full_module_path = f"sentientresearchagent.hierarchical_agent_framework.agent_configs.{module_path}"
            module = importlib.import_module(full_module_path)
            
            # Get the prompt attribute
            if not hasattr(module, attribute_name):
                raise AttributeError(f"Module {module_path} has no attribute {attribute_name}")
            
            prompt = getattr(module, attribute_name)
            
            if not isinstance(prompt, str):
                raise TypeError(f"Prompt {prompt_source} is not a string, got {type(prompt)}")
            
            return prompt
            
        except Exception as e:
            logger.error(f"Failed to resolve prompt {prompt_source}: {e}")
            raise
    
    def validate_agent_config(self, agent_config: DictConfig) -> List[str]:
        """
        Validate a single agent configuration.
        
        Args:
            agent_config: Agent configuration to validate
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Required fields
        required_fields = ["name", "type", "adapter_class"]
        for field in required_fields:
            if field not in agent_config:
                errors.append(f"Missing required field: {field}")
        
        # Validate agent type
        valid_types = ["planner", "executor", "aggregator", "atomizer", "plan_modifier", "custom_search"]
        if "type" in agent_config and agent_config.type not in valid_types:
            errors.append(f"Invalid agent type: {agent_config.type}. Must be one of {valid_types}")
        
        # Validate prompt source if present
        if "prompt_source" in agent_config:
            try:
                self.resolve_prompt(agent_config.prompt_source)
            except Exception as e:
                errors.append(f"Invalid prompt_source: {e}")
        
        # Validate model configuration if present
        if "model" in agent_config:
            model_config = agent_config.model
            if "provider" not in model_config or "model_id" not in model_config:
                errors.append("Model configuration must include 'provider' and 'model_id'")
        
        # Validate registration configuration
        if "registration" not in agent_config:
            errors.append("Missing registration configuration")
        else:
            reg_config = agent_config.registration
            if "action_keys" not in reg_config and "named_keys" not in reg_config:
                errors.append("Registration must include either 'action_keys' or 'named_keys'")
        
        return errors
    
    def validate_config(self, config: DictConfig) -> Dict[str, Any]:
        """
        Validate the entire agent configuration.
        
        Args:
            config: Configuration to validate
        
        Returns:
            Dictionary with validation results
        """
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "agent_count": len(config.agents),
            "enabled_count": 0,
            "disabled_count": 0
        }
        
        agent_names = set()
        
        for i, agent_config in enumerate(config.agents):
            # Check for duplicate names
            if agent_config.name in agent_names:
                validation_result["errors"].append(f"Duplicate agent name: {agent_config.name}")
            else:
                agent_names.add(agent_config.name)
            
            # Validate individual agent
            agent_errors = self.validate_agent_config(agent_config)
            for error in agent_errors:
                validation_result["errors"].append(f"Agent {agent_config.name}: {error}")
            
            # Count enabled/disabled
            if agent_config.get("enabled", True):
                validation_result["enabled_count"] += 1
            else:
                validation_result["disabled_count"] += 1
        
        validation_result["valid"] = len(validation_result["errors"]) == 0
        
        return validation_result


def load_agent_configs(config_dir: Optional[Path] = None) -> DictConfig:
    """
    Convenience function to load agent configurations.
    
    Args:
        config_dir: Directory containing configuration files
    
    Returns:
        Loaded and validated configuration
    """
    loader = AgentConfigLoader(config_dir)
    config = loader.load_config()
    
    # Validate configuration
    validation = loader.validate_config(config)
    
    if not validation["valid"]:
        logger.error("Agent configuration validation failed:")
        for error in validation["errors"]:
            logger.error(f"  - {error}")
        raise ValueError("Invalid agent configuration")
    
    if validation["warnings"]:
        logger.warning("Agent configuration warnings:")
        for warning in validation["warnings"]:
            logger.warning(f"  - {warning}")
    
    logger.info(f"✅ Agent configuration validated: {validation['enabled_count']} enabled, {validation['disabled_count']} disabled")
    
    return config 