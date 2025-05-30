"""
System Manager Service

Centralized management of all Sentient Research Agent components.
"""

import sys
import traceback
import os
from typing import Dict, Any, Optional
from loguru import logger

from ...config_utils import auto_load_config, validate_config
from ...cache.cache_manager import init_cache_manager
from ...error_handler import ErrorHandler, set_error_handler
from ...exceptions import handle_exception
from ...hierarchical_agent_framework.graph.task_graph import TaskGraph
from ...hierarchical_agent_framework.context.knowledge_store import KnowledgeStore
from ...hierarchical_agent_framework.graph.state_manager import StateManager
from ...hierarchical_agent_framework.node.hitl_coordinator import HITLCoordinator
from ...hierarchical_agent_framework.node.node_processor import NodeProcessor
from ...hierarchical_agent_framework.graph.execution_engine import ExecutionEngine
from ...simple_api import create_node_processor_config_from_main_config, SimpleSentientAgent

# Import WebSocket HITL utils with error handling
try:
    from ...hierarchical_agent_framework.utils.websocket_hitl_utils import (
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


class SystemManager:
    """
    Centralized system manager for all Sentient Research Agent components.
    
    This class handles initialization, configuration, and coordination of all
    system components including the task graph, knowledge store, execution engine,
    and various services.
    """
    
    def __init__(self):
        self.config = None
        self.task_graph = None
        self.knowledge_store = None
        self.state_manager = None
        self.hitl_coordinator = None
        self.node_processor = None
        self.execution_engine = None
        self.cache_manager = None
        self.error_handler = None
        self.simple_agent_instance = None
        self._initialized = False
        self._websocket_hitl_ready = False
    
    def initialize(self) -> Dict[str, Any]:
        """
        Initialize all Sentient systems with proper integration.
        
        Returns:
            Dictionary containing all initialized components
        """
        if self._initialized:
            logger.warning("System already initialized")
            return self.get_components()
            
        try:
            logger.info("🔧 Initializing Sentient Research Agent systems...")
            
            # 1. Load and validate configuration
            logger.info("📋 Loading configuration...")
            self.config = auto_load_config()
            
            validation = validate_config(self.config)
            if not validation["valid"]:
                logger.warning("Configuration issues found:")
                for issue in validation["issues"]:
                    logger.warning(f"   - {issue}")
            
            if validation["warnings"]:
                logger.warning("Configuration warnings:")
                for warning in validation["warnings"]:
                    logger.warning(f"   - {warning}")
            
            # 2. Setup logging from config
            self.config.setup_logging()
            
            # 3. Initialize error handling
            logger.info("🛡️  Setting up error handling...")
            self.error_handler = ErrorHandler(enable_detailed_logging=True)
            set_error_handler(self.error_handler)
            
            # 4. Initialize cache manager
            logger.info("💾 Setting up cache system...")
            self.cache_manager = init_cache_manager(self.config.cache)
            
            # 5. Initialize agent registry
            logger.info("🤖 Initializing agent registry...")
            from ...hierarchical_agent_framework import agents
            from ...hierarchical_agent_framework.agents.registry import AGENT_REGISTRY, NAMED_AGENTS
            
            # NEW: Trigger YAML agent integration
            logger.info("🔄 Integrating YAML-based agents...")
            try:
                # Call the lazy integration function
                yaml_integration_results = agents.integrate_yaml_agents_lazy()
                
                if yaml_integration_results:
                    logger.info(f"✅ YAML Integration Results:")
                    logger.info(f"   📋 Action keys registered: {yaml_integration_results['registered_action_keys']}")
                    logger.info(f"   🏷️  Named keys registered: {yaml_integration_results['registered_named_keys']}")
                    logger.info(f"   ⏭️  Skipped agents: {yaml_integration_results['skipped_agents']}")
                    logger.info(f"   ❌ Failed registrations: {yaml_integration_results['failed_registrations']}")
                else:
                    logger.warning("⚠️  YAML integration returned no results - using legacy agents only")
                    
            except Exception as e:
                logger.error(f"❌ YAML agent integration failed: {e}")
                logger.info("Continuing with legacy agent system only...")
            
            logger.info(f"✅ Agent registry loaded: {len(AGENT_REGISTRY)} adapters, {len(NAMED_AGENTS)} named agents")
            
            # 6. Initialize core components
            logger.info("🧠 Initializing core components...")
            self.task_graph = TaskGraph()
            self.knowledge_store = KnowledgeStore()
            self.state_manager = StateManager(self.task_graph)
            
            # Create node processor config from main config
            node_processor_config = create_node_processor_config_from_main_config(self.config)
            
            self.hitl_coordinator = HITLCoordinator(config=node_processor_config)
            self.node_processor = NodeProcessor(
                task_graph=self.task_graph,
                knowledge_store=self.knowledge_store,
                config=self.config,
                node_processor_config=node_processor_config
            )
            self.execution_engine = ExecutionEngine(
                task_graph=self.task_graph,
                state_manager=self.state_manager,
                knowledge_store=self.knowledge_store,
                hitl_coordinator=self.hitl_coordinator,
                config=self.config,
                node_processor=self.node_processor
            )
            
            self._initialized = True
            logger.info("✅ All Sentient systems initialized successfully!")
            
            # Print system info
            self._log_system_info()
            
            return self.get_components()
            
        except Exception as e:
            logger.error(f"❌ System initialization error: {e}")
            traceback.print_exc()
            
            # Try to handle with error system if available
            try:
                handled_error = handle_exception(e, context={"component": "system_initialization"})
                logger.error(f"📋 Error details: {handled_error.to_dict()}")
            except:
                pass  # Error system not available yet
            
            sys.exit(1)
    
    def setup_websocket_hitl(self, socketio):
        """
        Setup WebSocket HITL integration.
        
        Args:
            socketio: SocketIO instance to use for HITL
        """
        if not self._initialized:
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
    
    def get_simple_agent(self) -> Optional[SimpleSentientAgent]:
        """
        Get or create a SimpleSentientAgent instance optimized for API use.
        
        Returns:
            SimpleSentientAgent instance or None if creation failed
        """
        if self.simple_agent_instance is None:
            try:
                # Create Simple API agent with HITL disabled for API endpoints
                # This allows the API to work without human intervention by default
                self.simple_agent_instance = SimpleSentientAgent.create(enable_hitl=False)
                logger.info("✅ SimpleSentientAgent initialized for API endpoints (HITL: disabled for automation)")
            except Exception as e:
                logger.error(f"❌ Failed to initialize SimpleSentientAgent: {e}")
                return None
        return self.simple_agent_instance
    
    def get_components(self) -> Dict[str, Any]:
        """
        Get all initialized components.
        
        Returns:
            Dictionary containing all system components
        """
        return {
            'config': self.config,
            'task_graph': self.task_graph,
            'knowledge_store': self.knowledge_store,
            'state_manager': self.state_manager,
            'hitl_coordinator': self.hitl_coordinator,
            'node_processor': self.node_processor,
            'execution_engine': self.execution_engine,
            'cache_manager': self.cache_manager,
            'error_handler': self.error_handler
        }
    
    def get_system_info(self) -> Dict[str, Any]:
        """
        Get system information and statistics.
        
        Returns:
            Dictionary containing system info
        """
        if not self._initialized:
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
            "initialized": self._initialized,
            "websocket_hitl_ready": self.is_websocket_hitl_ready(),
            "websocket_hitl_available": WEBSOCKET_HITL_AVAILABLE
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
