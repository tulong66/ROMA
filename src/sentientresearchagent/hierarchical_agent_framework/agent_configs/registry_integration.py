"""
Registry Integration

Bridges the new YAML-based agent configuration system with the existing registry.
Allows gradual migration from definitions/ to agent_configs/.
"""

from typing import Dict, Any, List, Tuple, Optional
from loguru import logger

from .config_loader import AgentConfigLoader, load_agent_configs
from .agent_factory import AgentFactory, create_agents_from_config
from sentientresearchagent.hierarchical_agent_framework.agents.registry import AGENT_REGISTRY, NAMED_AGENTS, register_agent_adapter
from sentientresearchagent.hierarchical_agent_framework.agents.base_adapter import BaseAdapter


class RegistryIntegrator:
    """Integrates YAML-configured agents into the existing registry system."""
    
    def __init__(self, config_loader: Optional[AgentConfigLoader] = None):
        """
        Initialize the registry integrator.
        
        Args:
            config_loader: Optional config loader. If None, creates a default one.
        """
        self.config_loader = config_loader or AgentConfigLoader()
        self.factory = AgentFactory(self.config_loader)
        self.created_agents: Dict[str, Dict[str, Any]] = {}
        
    def load_and_register_agents(self) -> Dict[str, Any]:
        """
        Load agents from YAML configuration and register them in the existing registry.
        
        Returns:
            Dictionary with registration results
        """
        try:
            logger.info("🔄 Starting YAML agent integration with existing registry...")
            
            # Load configuration
            config = self.config_loader.load_config()
            logger.info(f"📋 Loaded configuration for {len(config.agents)} agents")
            
            # Create agents
            self.created_agents = self.factory.create_all_agents(config)
            logger.info(f"🏭 Created {len(self.created_agents)} agents from configuration")
            
            # Register agents in existing registry
            registration_results = self._register_agents_in_existing_registry()
            
            logger.info("✅ YAML agent integration completed successfully")
            return registration_results
            
        except Exception as e:
            logger.error(f"❌ Failed to integrate YAML agents: {e}")
            raise
    
    def _register_agents_in_existing_registry(self) -> Dict[str, Any]:
        """Register created agents in the existing AGENT_REGISTRY and NAMED_AGENTS."""
        results = {
            "registered_action_keys": 0,
            "registered_named_keys": 0,
            "skipped_agents": 0,
            "failed_registrations": 0,
            "details": []
        }
        
        for agent_name, agent_info in self.created_agents.items():
            try:
                adapter = agent_info["adapter"]
                registration = agent_info["registration"]
                
                # DEBUG: Add detailed logging
                logger.info(f"🔍 DEBUG - Registering {agent_name}:")
                logger.info(f"   Adapter type: {type(adapter)}")
                logger.info(f"   Adapter class name: {type(adapter).__name__}")
                logger.info(f"   Is BaseAdapter: {isinstance(adapter, BaseAdapter)}")
                logger.info(f"   BaseAdapter type: {BaseAdapter}")
                logger.info(f"   Adapter MRO: {[cls.__name__ for cls in type(adapter).__mro__]}")
                
                if not isinstance(adapter, BaseAdapter):
                    logger.warning(f"⚠️  Agent {agent_name} adapter is not a BaseAdapter, skipping registry registration")
                    results["skipped_agents"] += 1
                    continue
                
                agent_details = {
                    "name": agent_name,
                    "type": agent_info["type"],
                    "action_keys_registered": [],
                    "named_keys_registered": [],
                    "errors": []
                }
                
                # Register by action keys
                for action_verb, task_type in registration["action_keys"]:
                    try:
                        register_agent_adapter(
                            adapter=adapter,
                            action_verb=action_verb,
                            task_type=task_type
                        )
                        agent_details["action_keys_registered"].append((action_verb, task_type))
                        results["registered_action_keys"] += 1
                        logger.debug(f"✅ Registered {agent_name} for action ({action_verb}, {task_type})")
                    except Exception as e:
                        error_msg = f"Failed to register action key ({action_verb}, {task_type}): {e}"
                        agent_details["errors"].append(error_msg)
                        logger.error(f"❌ {agent_name}: {error_msg}")
                        results["failed_registrations"] += 1
                
                # Register by named keys
                for named_key in registration["named_keys"]:
                    try:
                        register_agent_adapter(
                            adapter=adapter,
                            name=named_key
                        )
                        agent_details["named_keys_registered"].append(named_key)
                        results["registered_named_keys"] += 1
                        logger.debug(f"✅ Registered {agent_name} with name '{named_key}'")
                    except Exception as e:
                        error_msg = f"Failed to register named key '{named_key}': {e}"
                        agent_details["errors"].append(error_msg)
                        logger.error(f"❌ {agent_name}: {error_msg}")
                        results["failed_registrations"] += 1
                
                results["details"].append(agent_details)
                
            except Exception as e:
                logger.error(f"❌ Failed to register agent {agent_name}: {e}")
                results["failed_registrations"] += 1
        
        return results
    
    def get_registry_status(self) -> Dict[str, Any]:
        """Get current status of the agent registry."""
        return {
            "total_agent_registry_entries": len(AGENT_REGISTRY),
            "total_named_agents": len(NAMED_AGENTS),
            "yaml_agents_created": len(self.created_agents),
            "yaml_agent_names": list(self.created_agents.keys()),
            "registry_keys": list(AGENT_REGISTRY.keys()),
            "named_agent_keys": list(NAMED_AGENTS.keys())
        }
    
    def validate_integration(self) -> Dict[str, Any]:
        """Validate that YAML agents are properly integrated."""
        validation_results = {
            "valid": True,
            "issues": [],
            "yaml_agents_in_registry": 0,
            "yaml_agents_in_named": 0
        }
        
        for agent_name, agent_info in self.created_agents.items():
            adapter = agent_info["adapter"]
            registration = agent_info["registration"]
            
            # Check action key registrations
            for action_verb, task_type in registration["action_keys"]:
                key = (action_verb.lower(), task_type)
                if key in AGENT_REGISTRY and AGENT_REGISTRY[key] == adapter:
                    validation_results["yaml_agents_in_registry"] += 1
                else:
                    validation_results["issues"].append(
                        f"Agent {agent_name} not found in AGENT_REGISTRY for key {key}"
                    )
                    validation_results["valid"] = False
            
            # Check named registrations
            for named_key in registration["named_keys"]:
                if named_key in NAMED_AGENTS and NAMED_AGENTS[named_key] == adapter:
                    validation_results["yaml_agents_in_named"] += 1
                else:
                    validation_results["issues"].append(
                        f"Agent {agent_name} not found in NAMED_AGENTS for key '{named_key}'"
                    )
                    validation_results["valid"] = False
        
        return validation_results

    def load_and_register_profile(self, profile_name: str) -> Dict[str, Any]:
        """
        Load a specific profile and register any profile-specific agents.
        
        Args:
            profile_name: Name of the profile to load
            
        Returns:
            Registration results
        """
        try:
            from .profile_loader import ProfileLoader
            
            logger.info(f"🔄 Loading profile: {profile_name}")
            
            # Load the profile
            profile_loader = ProfileLoader()
            profile_config_raw = profile_loader.profiles_dir / f"{profile_name}.yaml"
            
            if not profile_config_raw.exists():
                raise FileNotFoundError(f"Profile {profile_name} not found")
            
            # Load raw config to get agents section
            from omegaconf import OmegaConf
            profile_config = OmegaConf.load(profile_config_raw)
            
            # Create any profile-specific agents
            profile_agents = self.factory.create_agents_for_profile(profile_config)
            
            if profile_agents:
                logger.info(f"📋 Created {len(profile_agents)} profile-specific agents")
                
                # Register the profile-specific agents
                self.created_agents.update(profile_agents)
                registration_results = self._register_agents_in_existing_registry()
                
                logger.info(f"✅ Profile {profile_name} integration completed")
                return registration_results
            else:
                logger.info(f"📋 Profile {profile_name} has no specific agents to register")
                return {
                    "registered_action_keys": 0,
                    "registered_named_keys": 0,
                    "skipped_agents": 0,
                    "failed_registrations": 0,
                    "details": []
                }
                
        except Exception as e:
            logger.error(f"❌ Failed to integrate profile {profile_name}: {e}")
            raise

    def validate_profile_integration(self, profile_name: str) -> Dict[str, Any]:
        """
        Validate that a profile's agents are properly integrated.
        
        Args:
            profile_name: Name of the profile to validate
            
        Returns:
            Validation results
        """
        try:
            from .profile_loader import ProfileLoader
            
            # Load the blueprint
            profile_loader = ProfileLoader()
            blueprint = profile_loader.load_profile(profile_name)
            
            # Validate using the factory
            validation = self.factory.validate_blueprint_agents(blueprint)
            
            return {
                "profile_name": profile_name,
                "blueprint_valid": validation["valid"],
                "missing_agents": validation["missing_agents"],
                "blueprint_agents": validation["blueprint_agents"],
                "available_agents": validation["available_agents"]
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to validate profile {profile_name}: {e}")
            return {
                "profile_name": profile_name,
                "blueprint_valid": False,
                "error": str(e)
            }


def integrate_yaml_agents() -> Dict[str, Any]:
    """
    Convenience function to integrate YAML agents into the existing registry.
    
    Returns:
        Integration results
    """
    integrator = RegistryIntegrator()
    return integrator.load_and_register_agents()


def get_integration_status() -> Dict[str, Any]:
    """
    Get the current integration status.
    
    Returns:
        Status information
    """
    integrator = RegistryIntegrator()
    return integrator.get_registry_status()


def integrate_profile(profile_name: str) -> Dict[str, Any]:
    """
    Convenience function to integrate a specific profile.
    
    Args:
        profile_name: Name of the profile to integrate
        
    Returns:
        Integration results
    """
    integrator = RegistryIntegrator()
    return integrator.load_and_register_profile(profile_name)


def validate_profile(profile_name: str) -> Dict[str, Any]:
    """
    Convenience function to validate a profile integration.
    
    Args:
        profile_name: Name of the profile to validate
        
    Returns:
        Validation results
    """
    integrator = RegistryIntegrator()
    return integrator.validate_profile_integration(profile_name) 