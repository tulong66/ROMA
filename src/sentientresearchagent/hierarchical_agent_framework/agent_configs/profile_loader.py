"""
Agent Profile Loader

Loads agent profiles from YAML files and creates AgentBlueprint instances.
"""

import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from loguru import logger

try:
    from omegaconf import OmegaConf, DictConfig
except ImportError:
    logger.error("OmegaConf not installed. Please install with: pip install omegaconf>=2.3.0")
    raise

from ..agent_blueprints import AgentBlueprint
from ..types import TaskType


class ProfileLoader:
    """Loads agent profiles from YAML configuration files."""
    
    def __init__(self, profiles_dir: Optional[Path] = None):
        """
        Initialize the profile loader.
        
        Args:
            profiles_dir: Directory containing profile YAML files.
                         If None, uses the profiles/ subdirectory of this module.
        """
        if profiles_dir is None:
            profiles_dir = Path(__file__).parent / "profiles"
        
        self.profiles_dir = Path(profiles_dir)
        
        # Validate profiles directory exists
        if not self.profiles_dir.exists():
            raise FileNotFoundError(f"Profiles directory not found: {self.profiles_dir}")
    
    def list_available_profiles(self) -> List[str]:
        """
        List all available profile names.
        
        Returns:
            List of profile names (without .yaml extension)
        """
        profile_files = list(self.profiles_dir.glob("*.yaml"))
        return [f.stem for f in profile_files]
    
    def load_profile(self, profile_name: str) -> AgentBlueprint:
        """
        Load a specific agent profile.
        
        Args:
            profile_name: Name of the profile to load (without .yaml extension)
            
        Returns:
            AgentBlueprint instance
            
        Raises:
            FileNotFoundError: If profile file doesn't exist
            ValueError: If profile configuration is invalid
        """
        profile_file = self.profiles_dir / f"{profile_name}.yaml"
        
        if not profile_file.exists():
            available = self.list_available_profiles()
            raise FileNotFoundError(
                f"Profile '{profile_name}' not found. Available profiles: {available}"
            )
        
        try:
            logger.info(f"Loading agent profile from: {profile_file}")
            config = OmegaConf.load(profile_file)
            
            # Validate basic structure
            if "profile" not in config:
                raise ValueError("Profile configuration must contain 'profile' section")
            
            profile_config = config.profile
            
            # Convert TaskType strings to enums for planner_adapter_names
            planner_adapter_names = {}
            if "planner_adapter_names" in profile_config:
                for task_type_str, agent_name in profile_config.planner_adapter_names.items():
                    try:
                        task_type = TaskType[task_type_str.upper()]
                        planner_adapter_names[task_type] = agent_name
                    except KeyError:
                        logger.warning(f"Invalid task type '{task_type_str}' in planner_adapter_names for profile '{profile_name}'")
            
            # Convert TaskType strings to enums for executor_adapter_names
            executor_adapter_names = {}
            if "executor_adapter_names" in profile_config:
                for task_type_str, agent_name in profile_config.executor_adapter_names.items():
                    try:
                        task_type = TaskType[task_type_str.upper()]
                        executor_adapter_names[task_type] = agent_name
                    except KeyError:
                        logger.warning(f"Invalid task type '{task_type_str}' in executor_adapter_names for profile '{profile_name}'")
            
            # Create AgentBlueprint instance
            blueprint = AgentBlueprint(
                name=profile_config.get("name", profile_name),
                description=profile_config.get("description", f"Agent profile: {profile_name}"),
                planner_adapter_names=planner_adapter_names,
                executor_adapter_names=executor_adapter_names,
                atomizer_adapter_name=profile_config.get("atomizer_adapter_name", "DefaultAtomizer"),
                aggregator_adapter_name=profile_config.get("aggregator_adapter_name", "DefaultAggregator"),
                plan_modifier_adapter_name=profile_config.get("plan_modifier_adapter_name", "PlanModifier"),
                default_planner_adapter_name=profile_config.get("default_planner_adapter_name"),
                default_executor_adapter_name=profile_config.get("default_executor_adapter_name"),
                default_node_agent_name_prefix=profile_config.get("default_node_agent_name_prefix")
            )
            
            logger.info(f"Successfully loaded profile '{profile_name}' with {len(planner_adapter_names)} planner mappings and {len(executor_adapter_names)} executor mappings")
            return blueprint
            
        except Exception as e:
            logger.error(f"Failed to load profile '{profile_name}': {e}")
            raise
    
    def load_all_profiles(self) -> Dict[str, AgentBlueprint]:
        """
        Load all available profiles.
        
        Returns:
            Dictionary mapping profile names to AgentBlueprint instances
        """
        profiles = {}
        available_profiles = self.list_available_profiles()
        
        for profile_name in available_profiles:
            try:
                profiles[profile_name] = self.load_profile(profile_name)
            except Exception as e:
                logger.error(f"Failed to load profile '{profile_name}': {e}")
                # Continue loading other profiles
        
        logger.info(f"Loaded {len(profiles)} agent profiles: {list(profiles.keys())}")
        return profiles


def load_profile(profile_name: str, profiles_dir: Optional[Path] = None) -> AgentBlueprint:
    """
    Convenience function to load a single profile.
    
    Args:
        profile_name: Name of the profile to load
        profiles_dir: Optional custom profiles directory
        
    Returns:
        AgentBlueprint instance
    """
    loader = ProfileLoader(profiles_dir)
    return loader.load_profile(profile_name)


def list_profiles(profiles_dir: Optional[Path] = None) -> List[str]:
    """
    Convenience function to list available profiles.
    
    Args:
        profiles_dir: Optional custom profiles directory
        
    Returns:
        List of available profile names
    """
    loader = ProfileLoader(profiles_dir)
    return loader.list_available_profiles() 