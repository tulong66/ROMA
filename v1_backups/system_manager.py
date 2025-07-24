"""
System Manager Service

Centralized management of all Sentient Research Agent components.
"""

import sys
import traceback
import os
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from loguru import logger

from ..config import SentientConfig
from ..config import auto_load_config, validate_config
from .cache.cache_manager import init_cache_manager
from .error_handler import ErrorHandler, set_error_handler
from ..hierarchical_agent_framework.graph.task_graph import TaskGraph
from ..hierarchical_agent_framework.context.knowledge_store import KnowledgeStore
from ..hierarchical_agent_framework.graph.state_manager import StateManager
# HITLCoordinator, NodeProcessor, and ExecutionEngine moved to TYPE_CHECKING to avoid circular import
from ..framework_entry import create_node_processor_config_from_main_config
from ..hierarchical_agent_framework.agent_configs.profile_loader import ProfileLoader
# AgentRegistry moved to local import to avoid circular import
from ..hierarchical_agent_framework.agent_configs.registry_integration import validate_profile

# Import WebSocket HITL utils with error handling
try:
    from ..hierarchical_agent_framework.utils.websocket_hitl_utils import (
        set_socketio_instance, 
        set_hitl_timeout, 
        is_websocket_hitl_ready,
        get_websocket_hitl_status
    )
    WEBSOCKET_HITL_AVAILABLE = True
except ImportError as e:
    logger.warning(f"WebSocket HITL functions not available: {e}")
    WEBSOCKET_HITL_AVAILABLE = False
    
    # Define fallback functions
    def set_socketio_instance(socketio):
        logger.warning("WebSocket HITL not available - using fallback")
    
    def set_hitl_timeout(timeout_seconds: float):
        logger.warning("WebSocket HITL not available - using fallback")
    
    def is_websocket_hitl_ready() -> bool:
        return False
    
    def get_websocket_hitl_status() -> Dict[str, Any]:
        return {
            "ready": False,
            "socketio_available": False,
            "connected_clients": 0,
            "pending_requests": 0,
            "timeout_seconds": 1800.0,
            "error": "WebSocket HITL functions not available"
        }

if TYPE_CHECKING: # For type hints only
    from ..framework_entry import SimpleSentientAgent
    from ..hierarchical_agent_framework.node.hitl_coordinator import HITLCoordinator
    from ..hierarchical_agent_framework.node.node_processor import NodeProcessor
    from ..hierarchical_agent_framework.graph.execution_engine import ExecutionEngine

class SystemManager:
    """
    Centralized system manager for all Sentient Research Agent components.
    
    This class handles initialization, configuration, and coordination of all
    system components including the task graph, knowledge store, execution engine,
    and various services.
    """
    
    def __init__(self, config: Optional[SentientConfig] = None):
        self.config: SentientConfig
        if config is None:
            logger.info("📋 SystemManager: No config provided, auto-loading...")
            self.config = auto_load_config()
        else:
            self.config = config
        
        # Create an isolated agent registry for this instance
        from ..hierarchical_agent_framework.agents.registry import AgentRegistry
        self.agent_registry = AgentRegistry()
        
        self.task_graph: Optional[TaskGraph] = None
        self.knowledge_store: Optional[KnowledgeStore] = None
        self.state_manager: Optional[StateManager] = None
        self.hitl_coordinator: Optional["HITLCoordinator"] = None
        self.node_processor: Optional["NodeProcessor"] = None
        self.execution_engine: Optional["ExecutionEngine"] = None
        self.cache_manager = None
        self.error_handler: Optional[ErrorHandler] = None
        self.simple_agent_instance: "Optional[SimpleSentientAgent]" = None
        
        self._initialized_core = False
        self._websocket_hitl_ready = False
        self._current_profile: Optional[str] = None

        self._perform_core_initialization()

    def _perform_core_initialization(self) -> None:
        """
        Initialize core non-profile-specific Sentient systems.
        This is called by __init__.
        """
        if self._initialized_core:
            logger.warning("SystemManager: Core systems already initialized.")
            return

        try:
            logger.info("🔧 SystemManager: Initializing core systems...")
            
            # 1. Validate configuration (already loaded in __init__)
            validation = validate_config(self.config)
            if not validation["valid"]:
                logger.warning("SystemManager: Configuration issues found:")
                for issue in validation["issues"]:
                    logger.warning(f"   - {issue}")
            
            if validation["warnings"]:
                logger.warning("SystemManager: Configuration warnings:")
                for warning in validation["warnings"]:
                    logger.warning(f"   - {warning}")
            
            # 2. Setup logging from config
            self.config.setup_logging()
            
            # 3. Initialize error handling
            logger.info("🛡️  SystemManager: Setting up error handling...")
            self.error_handler = ErrorHandler(enable_detailed_logging=True)
            set_error_handler(self.error_handler)
            
            # 4. Initialize cache manager
            logger.info("💾 SystemManager: Setting up cache system...")
            self.cache_manager = init_cache_manager(self.config.cache)
            
            # 5. Initialize agent registry (foundational, profiles will select from this)
            # This now uses the instance-specific registry.
            logger.info("🤖 SystemManager: Initializing agent registry...")
            from ..hierarchical_agent_framework import agents
            
            logger.info("🔄 SystemManager: Integrating YAML-based agents into instance registry...")
            try:
                # Pass the instance registry to be populated
                yaml_integration_results = agents.integrate_yaml_agents_lazy(self.agent_registry)
                if yaml_integration_results:
                    logger.info(f"✅ YAML Integration Results: {yaml_integration_results}")
                else:
                    logger.warning("⚠️ SystemManager: YAML integration returned no results.")
            except Exception as e:
                logger.error(f"❌ SystemManager: YAML agent integration failed: {e}")
            
            # Log from the instance registry
            num_adapters = len(self.agent_registry.get_all_registered_agents())
            num_named_agents = len(self.agent_registry.get_all_named_agents())
            logger.info(f"✅ SystemManager: Agent registry loaded: {num_adapters} adapters, {num_named_agents} named agents")
            
            # 6. MODIFIED: Keep only display-only components for backward compatibility
            # Execution components are now project-specific in ProjectExecutionContext
            logger.info("🧠 SystemManager: Initializing display-only HAF components...")
            from ..hierarchical_agent_framework.graph.task_graph import TaskGraph
            from ..hierarchical_agent_framework.context.knowledge_store import KnowledgeStore
            from ..hierarchical_agent_framework.graph.state_manager import StateManager
            
            self.task_graph = TaskGraph()  # Display-only graph
            self.knowledge_store = KnowledgeStore()  # Display-only store
            self.state_manager = StateManager(self.task_graph)  # Display-only state manager
            
            # Note: execution_engine, node_processor, and hitl_coordinator are now project-specific only

            self._initialized_core = True
            logger.info("✅ SystemManager: Core systems initialized successfully!")
            self._log_system_info()
            
        except Exception as e:
            logger.error(f"❌ SystemManager: Core system initialization error: {e}")
            traceback.print_exc()
            sys.exit(1)

    def initialize_with_profile(self, profile_name: str = "deep_research_agent") -> Dict[str, Any]:
        """
        Initialize or reconfigure system components based on a specific agent profile.
        Assumes core systems are already initialized by __init__.
        Sets the active_profile_name in the main SentientConfig.
        """
        if not self._initialized_core:
            logger.error("SystemManager: Core systems not initialized before applying profile. Forcing initialization.")
            self._perform_core_initialization() 

        logger.info(f"⚙️ SystemManager: Applying agent profile '{profile_name}'...")
        
        try:
            # 1. Load profile blueprint (primarily for validation and info, not for modifying SentientConfig.agents directly here)
            from ..hierarchical_agent_framework.agent_configs.profile_loader import ProfileLoader
            
            profile_loader = ProfileLoader() 
            profile_blueprint = profile_loader.load_profile(profile_name) # This may raise if profile not found
            if not profile_blueprint: # Should be redundant if load_profile raises
                raise ValueError(f"Profile '{profile_name}' not found or failed to load.")
            
            # 2. MODIFIED: Set the active profile name in the main configuration.
            # The NodeProcessor and ExecutionEngine will use this active_profile_name
            # to look up the profile blueprint and select appropriate agents from the registry.
            self.config.active_profile_name = profile_name
            logger.info(f"Updated self.config.active_profile_name to '{profile_name}'.")
            
            # 3. Validate the profile integration (checks if agents in blueprint are registered)
            # Pass the instance-specific registry for validation
            profile_validation_result = validate_profile(profile_name, self.agent_registry) 
            
            is_profile_valid = False
            validation_issues = []

            if isinstance(profile_validation_result, dict):
                is_profile_valid = profile_validation_result.get("valid", False) # Default to False if 'valid' key is missing
                validation_issues = profile_validation_result.get("issues", [])
                if not validation_issues and not is_profile_valid and not profile_validation_result: # Empty dict might mean valid if no issues
                    is_profile_valid = True 
            elif isinstance(profile_validation_result, list): # If it returns a list of issues
                is_profile_valid = not bool(profile_validation_result) # Valid if list is empty
                validation_issues = profile_validation_result
            elif profile_validation_result is None: # Some validators return None for success
                is_profile_valid = True
            else:
                logger.warning(f"Profile '{profile_name}' validation returned an unexpected type: {type(profile_validation_result)}. Assuming invalid.")
                is_profile_valid = False
                validation_issues = [f"Unexpected validation result type: {type(profile_validation_result)}"]


            if not is_profile_valid:
                logger.warning(f"Profile '{profile_name}' validation issues:")
                for issue in validation_issues:
                    logger.warning(f"  - {issue}")
                # Decide if this is a fatal error. For now, we'll proceed but log warnings.
                # If it should be fatal, raise an exception here.
                # raise ValueError(f"Profile '{profile_name}' failed validation: {validation_issues}")
            else:
                logger.info(f"Profile '{profile_name}' validated successfully.")

            # 4. BACKWARD COMPATIBILITY: Create execution components for non-server contexts
            # This ensures SentientAgent and ProfiledSentientAgent work as expected
            # especially for evaluation.py and other standalone usage
            if not hasattr(self, '_execution_components_created'):
                logger.info("🔧 SystemManager: Creating execution components for backward compatibility...")
                self._create_execution_components()
                self._execution_components_created = True
            
            self._current_profile = profile_name
            logger.info(f"✅ SystemManager: Successfully applied profile '{profile_name}'. Profile is ready for project-specific execution contexts.")
            
            self._log_system_info() 

            return self.get_components()

        except Exception as e:
            logger.error(f"❌ SystemManager: Failed to apply profile '{profile_name}': {e}")
            traceback.print_exc()
            raise

    def _create_execution_components(self):
        """
        Create execution components for backward compatibility.
        
        This method creates the execution components that SentientAgent expects
        to be available on the SystemManager. This is needed for standalone usage
        like evaluation.py and other non-server contexts.
        """
        try:
            from ..hierarchical_agent_framework.node.hitl_coordinator import HITLCoordinator
            from ..hierarchical_agent_framework.node.node_processor import NodeProcessor
            
            # Create node processor config
            node_processor_config = create_node_processor_config_from_main_config(self.config)
            
            # Create HITL coordinator
            self.hitl_coordinator = HITLCoordinator(config=node_processor_config)
            
            # Create trace manager for backward compatibility (with default project ID)
            from ..hierarchical_agent_framework.tracing.manager import TraceManager
            self.trace_manager = TraceManager(project_id="system_manager_default")
            
            # Create node processor
            self.node_processor = NodeProcessor(
                task_graph=self.task_graph,
                knowledge_store=self.knowledge_store,
                agent_registry=self.agent_registry,
                trace_manager=self.trace_manager,
                config=self.config,
                node_processor_config=node_processor_config,
                agent_blueprint=None  # Will use active_profile_name from config
            )
            
            # Create execution engine
            from ..hierarchical_agent_framework.graph.execution_engine import ExecutionEngine
            self.execution_engine = ExecutionEngine(
                task_graph=self.task_graph,
                state_manager=self.state_manager,
                knowledge_store=self.knowledge_store,
                hitl_coordinator=self.hitl_coordinator,
                config=self.config,
                node_processor=self.node_processor
            )
            
            logger.info("✅ SystemManager: Execution components created for backward compatibility")
            
        except Exception as e:
            logger.error(f"❌ SystemManager: Failed to create execution components: {e}")
            traceback.print_exc()
            raise

    def setup_websocket_hitl(self, socketio):
        """
        Setup WebSocket HITL integration.
        
        Args:
            socketio: SocketIO instance to use for HITL
        """
        if not self._initialized_core:
            raise RuntimeError("System must be initialized before setting up WebSocket HITL")
        
        if not WEBSOCKET_HITL_AVAILABLE:
            logger.warning("⚠️ WebSocket HITL functions not available - skipping setup")
            return
            
        # Enable WebSocket HITL
        os.environ['SENTIENT_USE_WEBSOCKET_HITL'] = 'true'
        
        # Set server connection info for cross-process communication
        os.environ['SENTIENT_SERVER_HOST'] = 'localhost'
        os.environ['SENTIENT_SERVER_PORT'] = '5000'
        
        # Set up WebSocket HITL instance
        set_socketio_instance(socketio)
        set_hitl_timeout(self.config.execution.hitl_timeout_seconds)
        
        # Mark WebSocket HITL as ready
        self._websocket_hitl_ready = True
        
        logger.info(f"✅ WebSocket HITL initialized with {self.config.execution.hitl_timeout_seconds}s timeout")
        logger.info(f"🔗 HTTP fallback configured for localhost:5000")
    
    def is_websocket_hitl_ready(self) -> bool:
        """Check if WebSocket HITL is ready for use"""
        if not WEBSOCKET_HITL_AVAILABLE:
            return False
        return self._websocket_hitl_ready and is_websocket_hitl_ready()
    
    def get_websocket_hitl_status(self) -> Dict[str, Any]:
        """Get detailed WebSocket HITL status"""
        if not WEBSOCKET_HITL_AVAILABLE:
            return {
                "ready": False,
                "socketio_available": False,
                "connected_clients": 0,
                "pending_requests": 0,
                "timeout_seconds": 1800.0,
                "error": "WebSocket HITL functions not available"
            }
        return get_websocket_hitl_status()
    
    def get_simple_agent(self) -> "Optional[SimpleSentientAgent]":
        """
        Get or create a SimpleSentientAgent instance optimized for API use.
        It will use the currently configured SystemManager state (config, profile).
        """
        if not self._initialized_core:
            logger.warning("SystemManager: Core not initialized. Cannot create SimpleSentientAgent yet.")
            self._perform_core_initialization()
            if not self._current_profile:
                logger.info("SystemManager: No profile active. Applying default for SimpleSentientAgent.")
                self.initialize_with_profile()

        if not self._current_profile and self._initialized_core:
            logger.warning("SystemManager: No profile active even after init. Defaulting for SimpleSentientAgent.")
            self.initialize_with_profile()

        # MODIFIED: Local import for SimpleSentientAgent instantiation
        from ..framework_entry import SimpleSentientAgent as ConcreteSimpleSentientAgent

        if self.simple_agent_instance is None:
            logger.info("SystemManager: Creating new SimpleSentientAgent instance...")
            self.simple_agent_instance = ConcreteSimpleSentientAgent(system_manager=self)
        else:
            logger.debug("SystemManager: Reusing existing SimpleSentientAgent instance.")

        return self.simple_agent_instance
    
    def get_components(self) -> Dict[str, Any]:
        """
        Get system components.
        
        Returns:
            Dictionary of available system components
        """
        components = {
            "config": self.config,
            "agent_registry": self.agent_registry,
            "cache_manager": self.cache_manager,
            "error_handler": self.error_handler,
            "task_graph": self.task_graph,
            "knowledge_store": self.knowledge_store,
            "state_manager": self.state_manager,
        }
        
        # Add execution components if they exist (backward compatibility)
        if hasattr(self, 'execution_engine') and self.execution_engine:
            components["execution_engine"] = self.execution_engine
        if hasattr(self, 'node_processor') and self.node_processor:
            components["node_processor"] = self.node_processor
        if hasattr(self, 'hitl_coordinator') and self.hitl_coordinator:
            components["hitl_coordinator"] = self.hitl_coordinator
        
        return components
    
    def get_system_info(self) -> Dict[str, Any]:
        """
        Get system information and statistics.
        
        Returns:
            Dictionary containing system info
        """
        if not self._initialized_core:
            return {"error": "System not initialized"}
        
        cache_stats = self.cache_manager.get_stats() if self.cache_manager else None
        error_stats = self.error_handler.get_error_stats() if self.error_handler else None
        
        return {
            "config": {
                "llm_provider": self.config.llm.provider,
                "llm_model": self.config.llm.model,
                "cache_enabled": self.config.cache.enabled,
                "cache_type": self.config.cache.cache_type,
                "max_concurrent_nodes": self.config.execution.max_concurrent_nodes,
                "environment": self.config.environment
            },
            "cache_stats": cache_stats,
            "error_stats": error_stats,
            "graph_stats": {
                "total_nodes": len(self.task_graph.nodes),
                "total_graphs": len(self.task_graph.graphs)
            },
            "websocket_hitl": self.get_websocket_hitl_status(),
            "initialized": self._initialized_core,
            "websocket_hitl_ready": self.is_websocket_hitl_ready(),
            "websocket_hitl_available": WEBSOCKET_HITL_AVAILABLE,
            "current_profile": self._current_profile,
            "available_profiles": self.get_available_profiles()
        }
    
    def _log_system_info(self):
        """Log system initialization information."""
        try:
            cache_stats = self.cache_manager.get_stats()
            logger.info(f"📊 Cache: {self.config.cache.cache_type} backend, {cache_stats['current_size']} items")
            logger.info(f"⚙️  Execution: max {self.config.execution.max_concurrent_nodes} concurrent nodes")
            logger.info(f"🔗 LLM: {self.config.llm.provider}/{self.config.llm.model}")
            logger.info(f"🎮 HITL Master: {'Enabled' if self.config.execution.enable_hitl else 'Disabled'}")
            
            if self.config.execution.enable_hitl:
                logger.info(f"   - Plan Generation: {getattr(self.config.execution, 'hitl_after_plan_generation', True)}")
                logger.info(f"   - Modified Plan: {getattr(self.config.execution, 'hitl_after_modified_plan', True)}")
                logger.info(f"   - Atomizer: {getattr(self.config.execution, 'hitl_after_atomizer', False)}")
                logger.info(f"   - Before Execute: {getattr(self.config.execution, 'hitl_before_execute', False)}")
                logger.info(f"   - WebSocket HITL Available: {WEBSOCKET_HITL_AVAILABLE}")
        except Exception as e:
            logger.warning(f"Failed to log system info: {e}")

    def get_available_profiles(self) -> List[str]:
        """Get list of available agent profiles."""
        try:
            loader = ProfileLoader()
            return loader.list_available_profiles()
        except Exception as e:
            logger.error(f"Failed to get available profiles: {e}")
            return []

    def get_profile_details(self, profile_name: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific profile.
        
        Args:
            profile_name: Name of the profile to get details for
            
        Returns:
            Dictionary containing profile details
        """
        try:
            loader = ProfileLoader()
            blueprint = loader.load_profile(profile_name)
            validation = validate_profile(profile_name, self.agent_registry)
            
            return {
                "name": blueprint.name,
                "description": blueprint.description,
                "root_planner": blueprint.root_planner_adapter_name,
                "planner_mappings": {str(k): v for k, v in blueprint.planner_adapter_names.items()},
                "executor_mappings": {str(k): v for k, v in blueprint.executor_adapter_names.items()},
                "atomizer": blueprint.atomizer_adapter_name,
                "aggregator": blueprint.aggregator_adapter_name,
                "plan_modifier": blueprint.plan_modifier_adapter_name,
                "default_planner": blueprint.default_planner_adapter_name,
                "default_executor": blueprint.default_executor_adapter_name,
                "recommended_for": ["Research Projects", "Data Analysis", "Report Writing"],
                "validation": validation,
                "is_valid": validation.get("blueprint_valid", False)
            }
        except Exception as e:
            logger.error(f"Failed to get profile details for {profile_name}: {e}")
            return {
                "name": profile_name,
                "error": str(e),
                "is_valid": False,
                "recommended_for": []
            }

    def get_current_profile(self) -> Optional[str]:
        """Get the currently active profile name."""
        return self._current_profile

    def get_profiles_with_current(self) -> Dict[str, Any]:
        """Get profiles list with current profile marked."""
        try:
            profiles = []
            available_profile_names = self.get_available_profiles()
            current_profile = self.get_current_profile()
            
            if not current_profile and available_profile_names:
                # Prioritize general_agent for data analysis tasks
                if "general_agent" in available_profile_names:
                    current_profile = "general_agent"
                elif "deep_research_agent" in available_profile_names:
                    current_profile = "deep_research_agent"
                else:
                    current_profile = available_profile_names[0]
                self._current_profile = current_profile
                logger.info(f"🎯 Auto-selected profile: {current_profile}")
            
            for profile_name in available_profile_names:
                profile_details = self.get_profile_details(profile_name)
                profile_details['is_current'] = (profile_name == current_profile)
                profiles.append(profile_details)
            
            return {
                "current_profile": current_profile,
                "profiles": profiles,
                "total_count": len(profiles)
            }
        except Exception as e:
            logger.error(f"Failed to get profiles with current: {e}")
            return {
                "current_profile": None,
                "profiles": [],
                "total_count": 0
            }

    def switch_profile(self, profile_name: str) -> Dict[str, Any]:
        """
        Switch to a different agent profile.
        
        Args:
            profile_name: Name of the profile to switch to
            
        Returns:
            Dictionary containing switch results and new system info
        """
        try:
            logger.info(f"🔄 Switching to profile: {profile_name}")
            
            validation = validate_profile(profile_name, self.agent_registry)
            
            if not validation.get("blueprint_valid", False):
                return {
                    "success": False,
                    "error": f"Profile '{profile_name}' is not valid",
                    "validation": validation
                }
            
            if self._initialized_core:
                logger.info("🧹 Clearing current system state...")
                self.task_graph.nodes.clear()
                self.task_graph.graphs.clear()
                self.task_graph.root_graph_id = None
                self.task_graph.overall_project_goal = None
                
                self._initialized_core = False
            
            components = self.initialize_with_profile(profile_name)
            self._current_profile = profile_name
            
            logger.success(f"✅ Successfully switched to profile: {profile_name}")
            
            return {
                "success": True,
                "profile": profile_name,
                "message": f"Successfully switched to {profile_name}",
                "system_info": self.get_system_info(),
                "profile_details": self.get_profile_details(profile_name)
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to switch profile to {profile_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "profile": profile_name
            }

    def clear_all_execution_state(self, task_graph, knowledge_store, cache_manager=None, project_id=None):
        """Clear all execution state to prevent data pollution."""
        # Clear task graph
        task_graph.nodes.clear()
        task_graph.graphs.clear()
        task_graph.root_graph_id = None
        task_graph.overall_project_goal = None
        
        # Clear knowledge store
        if hasattr(knowledge_store, 'clear_all_records'):
            knowledge_store.clear_all_records()
        elif hasattr(knowledge_store, 'clear'):
            knowledge_store.clear()
        else:
            # If no clear method, recreate the store
            knowledge_store.records.clear() if hasattr(knowledge_store, 'records') else None
        
        # Clear cache if available
        if cache_manager and project_id:
            cache_manager.clear_namespace(f"project_{project_id}")
        
        # NOTE: Trace data is now project-specific and automatically cleaned up
        # when ProjectExecutionContext instances are destroyed
        
        logger.info("✅ All execution state cleared successfully")
