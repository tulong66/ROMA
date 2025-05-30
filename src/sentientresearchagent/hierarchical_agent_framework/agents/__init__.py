from loguru import logger

# Import only the registry components we need
from .registry import (
    AGENT_REGISTRY, # Expose for potential direct use or inspection
    NAMED_AGENTS    # Expose for potential direct use or inspection
)

logger.info("🤖 Initializing YAML-based agent system...")

# YAML-based agent integration (replaces legacy system)
def integrate_yaml_agents_lazy():
    """Load and integrate YAML-configured agents."""
    try:
        from ..agent_configs.registry_integration import integrate_yaml_agents
        
        logger.info("🔄 Loading YAML-based agents...")
        integration_results = integrate_yaml_agents()
        
        logger.info(f"✅ YAML Agent Integration Results:")
        logger.info(f"   📋 Action keys registered: {integration_results['registered_action_keys']}")
        logger.info(f"   🏷️  Named keys registered: {integration_results['registered_named_keys']}")
        logger.info(f"   ⏭️  Skipped agents: {integration_results['skipped_agents']}")
        logger.info(f"   ❌ Failed registrations: {integration_results['failed_registrations']}")
        
        # Log final registry state
        logger.info(f"📊 Final registry state - AGENT_REGISTRY: {len(AGENT_REGISTRY)} entries")
        logger.info(f"📊 Final registry state - NAMED_AGENTS: {len(NAMED_AGENTS)} entries")
        
        return integration_results
        
    except Exception as e:
        logger.error(f"❌ Failed to integrate YAML agents: {e}")
        logger.error("🚨 No agents will be available! Check your YAML configuration.")
        return None

# Store the lazy loader for later use
_yaml_integration_loader = integrate_yaml_agents_lazy

# Final check
if not AGENT_REGISTRY and not NAMED_AGENTS:
    logger.warning("⚠️  Warning: No agent adapters or named agents were registered.")
    logger.warning("The system might not find agents to process tasks.")
else:
    logger.info("✅ Agent system initialization completed successfully")
