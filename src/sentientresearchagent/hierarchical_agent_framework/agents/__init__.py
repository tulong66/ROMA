from loguru import logger

# Import configurations and registry functions
from .configurations import AGENT_CONFIGURATIONS
from .registry import (
    initialize_adapters_from_configurations,
    register_special_cases,
    AGENT_REGISTRY, # Expose for potential direct use or inspection
    NAMED_AGENTS    # Expose for potential direct use or inspection
)

logger.info("Executing agents/__init__.py: Initializing agent adapters...")

# Process standard configurations
if AGENT_CONFIGURATIONS:
    initialize_adapters_from_configurations(AGENT_CONFIGURATIONS)
else:
    logger.warning("AGENT_CONFIGURATIONS list is empty. No standard adapters will be initialized from it.")

# Handle any special registration cases
# This function will internally decide what to do based on availability of agents/adapters
register_special_cases()

logger.info(f"AGENT_REGISTRY populated: {len(AGENT_REGISTRY)} entries.")
logger.info(f"NAMED_AGENTS populated: {len(NAMED_AGENTS)} entries.")

if not AGENT_REGISTRY and not NAMED_AGENTS:
    logger.warning("Warning: No agent adapters or named agents were registered. "
                   "The system might not find agents to process tasks.")

# Clean up imports that are no longer directly used in __init__.py
# Specific adapters, Agno agents, BaseAdapter, TaskType, etc.,
# are now primarily used in configurations.py or registry.py.

# Expose key components if needed elsewhere, though direct imports are preferred.
# For example, if some other module needed direct access to AGENT_REGISTRY,
# it's already imported and thus available via from . import AGENT_REGISTRY
