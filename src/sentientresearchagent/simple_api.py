"""
Unified entry point for the Sentient Research Agent framework.
This provides a single, easy-to-use API that integrates all system components
with proper configuration management.
"""

from typing import Dict, Any, Optional, Union, Iterator
from pathlib import Path
from datetime import datetime
import uuid
import asyncio
import nest_asyncio  # Add this import

from loguru import logger

try:
    # Import existing framework components
    from .hierarchical_agent_framework.graph.task_graph import TaskGraph
    from .hierarchical_agent_framework.graph.state_manager import StateManager
    from .hierarchical_agent_framework.graph.execution_engine import ExecutionEngine
    from .hierarchical_agent_framework.node.node_processor import NodeProcessor
    from .hierarchical_agent_framework.context.knowledge_store import KnowledgeStore
    from .hierarchical_agent_framework.node.node_configs import NodeProcessorConfig
    from .hierarchical_agent_framework.node.hitl_coordinator import HITLCoordinator

    # Import configuration system
    from .config import load_config, SentientConfig
    from .config_utils import auto_load_config, validate_config

    # Import supporting systems
    from .cache.cache_manager import init_cache_manager
    from .error_handler import get_error_handler, set_error_handler, ErrorHandler
    from .exceptions import SentientError, handle_exception

    FRAMEWORK_AVAILABLE = True
    
except ImportError as e:
    logger.error(f"Framework components not available: {e}")
    FRAMEWORK_AVAILABLE = False


def find_config_file() -> Optional[Path]:
    """
    Find configuration file using comprehensive search paths.
    
    Search order:
    1. ./sentient.yaml (primary)
    2. ./config.yaml (common alternative)
    3. ./sentient.yml
    4. ~/.sentient/config.yaml
    5. ~/.sentient/config.yml
    6. /etc/sentient/config.yaml
    
    Returns:
        Path to configuration file if found, None otherwise
    """
    search_paths = [
        Path("./sentient.yaml"),      # Primary config file
        Path("./config.yaml"),        # Common alternative
        Path("./sentient.yml"),
        Path.home() / ".sentient" / "config.yaml",
        Path.home() / ".sentient" / "config.yml",
        Path("/etc/sentient/config.yaml"),
    ]
    
    for path in search_paths:
        if path.exists() and path.is_file():
            logger.info(f"Found configuration file: {path}")
            return path
    
    logger.warning("No configuration file found, will use environment variables and defaults")
    return None


def load_unified_config(config_path: Optional[Union[str, Path]] = None) -> SentientConfig:
    """
    Load configuration with unified approach.
    
    Args:
        config_path: Optional explicit path to config file
        
    Returns:
        SentientConfig instance
    """
    if config_path:
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        logger.info(f"Loading configuration from: {config_path}")
        config = load_config(config_file=config_path, use_env=True)
    else:
        # Auto-discover configuration
        found_config = find_config_file()
        if found_config:
            config = load_config(config_file=found_config, use_env=True)
        else:
            logger.info("Loading configuration from environment variables and defaults")
            config = load_config(use_env=True)
    
    return config


def create_node_processor_config_from_main_config(main_config: SentientConfig) -> NodeProcessorConfig:
    """
    Create NodeProcessorConfig from the centralized main configuration.
    """
    node_config = NodeProcessorConfig()
    
    # Map centralized config to NodeProcessorConfig
    if main_config.execution.enable_hitl:
        if main_config.execution.hitl_root_plan_only:
            # NEW: Root plan only mode - only enable plan generation for root nodes
            node_config.enable_hitl_after_plan_generation = True  # Will be filtered by layer in HITLCoordinator
            node_config.enable_hitl_after_modified_plan = True  # FIXED: Keep this enabled for modification loop
            node_config.enable_hitl_after_atomizer = False
            node_config.enable_hitl_before_execute = False
            logger.debug("HITL configured for root plan only (with modification reviews)")
        else:
            # Normal HITL mode - use all configured checkpoints
            node_config.enable_hitl_after_plan_generation = main_config.execution.hitl_after_plan_generation
            node_config.enable_hitl_after_modified_plan = main_config.execution.hitl_after_modified_plan
            node_config.enable_hitl_after_atomizer = main_config.execution.hitl_after_atomizer
            node_config.enable_hitl_before_execute = main_config.execution.hitl_before_execute
            logger.debug("HITL configured for all enabled checkpoints")
    else:
        # If master HITL is disabled, disable all checkpoints
        node_config.enable_hitl_after_plan_generation = False
        node_config.enable_hitl_after_modified_plan = False
        node_config.enable_hitl_after_atomizer = False
        node_config.enable_hitl_before_execute = False
        logger.debug("HITL disabled - all checkpoints off")
    
    # NEW: Store the root_plan_only flag for HITLCoordinator to use
    node_config.hitl_root_plan_only = getattr(main_config.execution, 'hitl_root_plan_only', False)
    
    logger.debug(f"NodeProcessorConfig created: plan_gen={node_config.enable_hitl_after_plan_generation}, "
                f"modified_plan={node_config.enable_hitl_after_modified_plan}, "
                f"atomizer={node_config.enable_hitl_after_atomizer}, "
                f"before_exec={node_config.enable_hitl_before_execute}, "
                f"root_only={getattr(node_config, 'hitl_root_plan_only', False)}")
    
    return node_config


def initialize_system(config: SentientConfig) -> Dict[str, Any]:
    """
    Initialize all system components with proper integration.
    
    Args:
        config: Configuration to use for initialization
        
    Returns:
        Dictionary containing all initialized components
    """
    logger.info("🔧 Initializing Sentient Research Agent system...")
    
    try:
        # 1. Setup logging from config
        config.setup_logging()
        logger.info("📋 Configuration loaded and logging configured")
        
        # 2. Initialize error handling
        logger.info("🛡️  Setting up error handling...")
        error_handler = ErrorHandler(enable_detailed_logging=True)
        set_error_handler(error_handler)
        
        # 3. Initialize cache manager
        logger.info("💾 Setting up cache system...")
        cache_manager = init_cache_manager(config.cache)
        
        # 4. Initialize agent registry
        logger.info("🤖 Initializing agent registry...")
        from .hierarchical_agent_framework import agents
        from .hierarchical_agent_framework.agents.registry import AGENT_REGISTRY, NAMED_AGENTS
        logger.info(f"✅ Agent registry loaded: {len(AGENT_REGISTRY)} adapters, {len(NAMED_AGENTS)} named agents")
        
        # 5. Initialize core components
        logger.info("🧠 Initializing core components...")
        task_graph = TaskGraph()
        knowledge_store = KnowledgeStore()
        state_manager = StateManager(task_graph)
        
        # Create node processor config from main config
        node_processor_config = create_node_processor_config_from_main_config(config)
        
        hitl_coordinator = HITLCoordinator(config=node_processor_config)
        node_processor = NodeProcessor(
            task_graph=task_graph,
            knowledge_store=knowledge_store,
            config=config,
            node_processor_config=node_processor_config
        )
        execution_engine = ExecutionEngine(
            task_graph=task_graph,
            state_manager=state_manager,
            knowledge_store=knowledge_store,
            hitl_coordinator=hitl_coordinator,
            config=config,
            node_processor=node_processor
        )
        
        # 6. Print system info
        cache_stats = cache_manager.get_stats()
        logger.info("✅ All systems initialized successfully!")
        logger.info(f"📊 Cache: {config.cache.cache_type} backend, {cache_stats['current_size']} items")
        logger.info(f"⚙️  Execution: max {config.execution.max_concurrent_nodes} concurrent nodes")
        logger.info(f"🔗 LLM: {config.llm.provider}/{config.llm.model}")
        logger.info(f"🎮 HITL: {'Enabled' if config.execution.enable_hitl else 'Disabled'}")
        
        return {
            'config': config,
            'task_graph': task_graph,
            'knowledge_store': knowledge_store,
            'state_manager': state_manager,
            'hitl_coordinator': hitl_coordinator,
            'node_processor': node_processor,
            'execution_engine': execution_engine,
            'cache_manager': cache_manager,
            'error_handler': error_handler
        }
        
    except Exception as e:
        logger.error(f"❌ System initialization error: {e}")
        
        # Try to handle with error system if available
        try:
            handled_error = handle_exception(e, context={"component": "system_initialization"})
            logger.error(f"📋 Error details: {handled_error.to_dict()}")
        except:
            pass  # Error system not available yet
        
        raise


class SentientAgent:
    """
    Unified entry point for the Sentient Research Agent framework.
    
    This class provides a single, easy-to-use API that integrates all system
    components with proper configuration management.
    """
    
    def __init__(self, config: Optional[SentientConfig] = None, enable_hitl: Optional[bool] = None):
        """
        Initialize the agent with configuration.
        
        Args:
            config: Optional custom configuration. If None, auto-loads from files/environment.
            enable_hitl: Optional override for master HITL setting.
        """
        if not FRAMEWORK_AVAILABLE:
            raise ImportError("Framework components not available. Please check installation.")
        
        # Load configuration
        if config is None:
            self.config = load_unified_config()
            logger.info("Configuration auto-loaded from files/environment")
        else:
            self.config = config
            logger.info("Using provided custom configuration")
        
        # Override HITL setting if specified
        if enable_hitl is not None:
            original_hitl = self.config.execution.enable_hitl
            self.config.execution.enable_hitl = enable_hitl
            logger.info(f"HITL override: {original_hitl} -> {enable_hitl}")
        
        # Initialize all system components
        self.systems = initialize_system(self.config)
        
        # Extract components for easy access
        self.task_graph = self.systems['task_graph']
        self.knowledge_store = self.systems['knowledge_store']
        self.state_manager = self.systems['state_manager']
        self.hitl_coordinator = self.systems['hitl_coordinator']
        self.node_processor = self.systems['node_processor']
        self.execution_engine = self.systems['execution_engine']
        self.cache_manager = self.systems['cache_manager']
        self.error_handler = self.systems['error_handler']
        
        logger.info(f"SentientAgent initialized (HITL: {'enabled' if self.config.execution.enable_hitl else 'disabled'})")
    
    @classmethod
    def create(
        cls, 
        config_path: Optional[Union[str, Path]] = None,
        enable_hitl: Optional[bool] = None,
        hitl_root_plan_only: Optional[bool] = None,
        **config_overrides
    ) -> "SentientAgent":
        """
        Create agent with flexible configuration options.
        
        Args:
            config_path: Optional path to YAML configuration file
            enable_hitl: Optional override for master HITL setting
            hitl_root_plan_only: Optional override to only review root node's plan
            **config_overrides: Direct configuration overrides
        
        Returns:
            SentientAgent instance
            
        Examples:
            >>> # Auto-load config from sentient.yaml
            >>> agent = SentientAgent.create()
            
            >>> # Use specific config file
            >>> agent = SentientAgent.create(config_path="my_config.yaml")
            
            >>> # Only review the root plan, not sub-plans
            >>> agent = SentientAgent.create(
            ...     enable_hitl=True,
            ...     hitl_root_plan_only=True
            ... )
            
            >>> # Override specific settings
            >>> agent = SentientAgent.create(
            ...     enable_hitl=False,
            ...     model="gpt-3.5-turbo",
            ...     max_steps=100
            ... )
        """
        if not FRAMEWORK_AVAILABLE:
            raise ImportError("Framework components not available. Please check installation.")
        
        # Load configuration
        config = load_unified_config(config_path)
        
        # Apply direct overrides
        if config_overrides:
            logger.info(f"Applying config overrides: {list(config_overrides.keys())}")
            
            # Handle common overrides
            if 'model' in config_overrides:
                config.llm.model = config_overrides['model']
            if 'temperature' in config_overrides:
                config.llm.temperature = config_overrides['temperature']
            if 'max_steps' in config_overrides:
                config.execution.max_execution_steps = config_overrides['max_steps']
            if 'provider' in config_overrides:
                config.llm.provider = config_overrides['provider']
            if 'max_concurrent_nodes' in config_overrides:
                config.execution.max_concurrent_nodes = config_overrides['max_concurrent_nodes']
            if 'api_key' in config_overrides:
                config.llm.api_key = config_overrides['api_key']
        
        # NEW: Apply HITL overrides
        if enable_hitl is not None:
            config.execution.enable_hitl = enable_hitl
        
        if hitl_root_plan_only is not None:
            config.execution.hitl_root_plan_only = hitl_root_plan_only
            # If enabling root plan only, ensure HITL is enabled
            if hitl_root_plan_only and not config.execution.enable_hitl:
                config.execution.enable_hitl = True
                logger.info("Automatically enabled HITL because hitl_root_plan_only=True")
        
        return cls(config)
    
    def execute(self, goal: str, **options) -> Dict[str, Any]:
        """
        Execute a goal using the sophisticated agent system.
        
        Args:
            goal: The high-level goal to achieve
            **options: Additional options:
                - max_steps: Maximum execution steps (overrides config)
                - enable_hitl: Enable HITL for this execution only
                - hitl_root_plan_only: Only review root node's plan for this execution
                - save_state: Whether to save execution state (default: True)
        
        Returns:
            Dictionary with execution results including:
            - execution_id: Unique identifier for this execution
            - goal: The original goal
            - status: 'completed', 'failed', or 'partial'
            - final_output: The main result
            - execution_time: Time taken in seconds
            - node_count: Number of nodes created
            - hitl_enabled: Whether HITL was enabled
            - hitl_root_plan_only: Whether only root plan was reviewed
        """
        start_time = datetime.now()
        execution_id = f"exec_{uuid.uuid4().hex[:8]}"
        execution_result = None
        
        try:
            logger.info(f"[{execution_id}] Starting execution: {goal[:100]}...")
            
            # Get options
            max_steps = options.get('max_steps', self.config.execution.max_execution_steps)
            enable_hitl_override = options.get('enable_hitl')
            hitl_root_plan_only_override = options.get('hitl_root_plan_only')
            save_state = options.get('save_state', True)
            
            # Temporarily override HITL if specified
            original_hitl_setting = self.config.execution.enable_hitl
            original_root_plan_only_setting = getattr(self.config.execution, 'hitl_root_plan_only', False)
            original_node_config = None
            
            config_changed = False
            
            if enable_hitl_override is not None:
                self.config.execution.enable_hitl = enable_hitl_override
                config_changed = True
            
            # NEW: Handle root plan only override
            if hitl_root_plan_only_override is not None:
                self.config.execution.hitl_root_plan_only = hitl_root_plan_only_override
                # If enabling root plan only, ensure HITL is enabled
                if hitl_root_plan_only_override and not self.config.execution.enable_hitl:
                    self.config.execution.enable_hitl = True
                    logger.info(f"[{execution_id}] Automatically enabled HITL because hitl_root_plan_only=True")
                config_changed = True
            
            if config_changed:
                # Recreate NodeProcessorConfig with new HITL settings
                original_node_config = self.node_processor.node_processor_config
                new_node_config = create_node_processor_config_from_main_config(self.config)
                
                # Update both the node processor AND the HITL coordinator
                self.node_processor.node_processor_config = new_node_config
                self.hitl_coordinator.config = new_node_config
                
                logger.info(f"[{execution_id}] HITL settings overridden - "
                           f"enabled: {self.config.execution.enable_hitl}, "
                           f"root_only: {getattr(self.config.execution, 'hitl_root_plan_only', False)}")
            
            try:
                # Clear previous state
                self.task_graph.nodes.clear()
                self.task_graph.graphs.clear()
                self.task_graph.root_graph_id = None
                self.task_graph.overall_project_goal = None
                
                # Run the async execution - JUPYTER SAFE
                execution_result = _run_async_safely(self._run_async_execution(goal, max_steps))
                
                # Extract results
                final_output = self._extract_final_result()
                execution_time = (datetime.now() - start_time).total_seconds()
                node_count = len(self.task_graph.nodes)
                
                result = {
                    'execution_id': execution_id,
                    'goal': goal,
                    'status': 'completed',
                    'final_output': final_output,
                    'execution_time': execution_time,
                    'node_count': node_count,
                    'hitl_enabled': self.config.execution.enable_hitl,
                    'hitl_root_plan_only': getattr(self.config.execution, 'hitl_root_plan_only', False),
                    'config_source': 'config_file' if find_config_file() else 'defaults',
                    'framework_result': execution_result,
                    'environment': 'jupyter' if _is_jupyter_environment() else 'python'
                }
                
                # Save state if requested
                if save_state:
                    self._save_execution_state(execution_id, result)
                
                logger.info(f"[{execution_id}] Execution completed: {node_count} nodes, {execution_time:.2f}s")
                return result
                
            finally:
                # Restore original HITL settings AND NodeProcessorConfig
                if config_changed:
                    self.config.execution.enable_hitl = original_hitl_setting
                    self.config.execution.hitl_root_plan_only = original_root_plan_only_setting
                    if original_node_config:
                        self.node_processor.node_processor_config = original_node_config
                        self.hitl_coordinator.config = original_node_config
                        logger.debug(f"[{execution_id}] Restored original HITL configuration")
        
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"[{execution_id}] Execution failed: {e}")
            
            return {
                'execution_id': execution_id,
                'goal': goal,
                'status': 'failed',
                'error': str(e),
                'execution_time': execution_time,
                'node_count': len(self.task_graph.nodes),
                'hitl_enabled': self.config.execution.enable_hitl,
                'hitl_root_plan_only': getattr(self.config.execution, 'hitl_root_plan_only', False),
                'framework_result': execution_result,
                'environment': 'jupyter' if _is_jupyter_environment() else 'python'
            }
    
    async def _run_async_execution(self, goal: str, max_steps: int):
        """Run the async execution flow"""
        return await self.execution_engine.run_project_flow(
            root_goal=goal,
            max_steps=max_steps
        )
    
    def stream_execution(self, goal: str, **options) -> Iterator[Dict[str, Any]]:
        """
        Stream execution progress in real-time.
        
        Args:
            goal: The high-level goal to achieve
            **options: Same as execute() method
            
        Yields:
            Progress updates with status, message, and current state
        """
        execution_id = f"stream_{uuid.uuid4().hex[:8]}"
        
        try:
            yield {
                'execution_id': execution_id,
                'status': 'initializing',
                'message': f'Starting: {goal[:50]}...',
                'progress': 0,
                'hitl_enabled': self.config.execution.enable_hitl,
                'environment': 'jupyter' if _is_jupyter_environment() else 'python'
            }
            
            # Get options
            max_steps = options.get('max_steps', self.config.execution.max_execution_steps)
            enable_hitl_override = options.get('enable_hitl')
            
            # Temporarily override HITL if specified
            original_hitl_setting = self.config.execution.enable_hitl
            original_node_config = None
            
            if enable_hitl_override is not None:
                self.config.execution.enable_hitl = enable_hitl_override
                original_node_config = self.node_processor.node_processor_config
                new_node_config = create_node_processor_config_from_main_config(self.config)
                self.node_processor.node_processor_config = new_node_config
                self.hitl_coordinator.config = new_node_config
            
            try:
                yield {
                    'execution_id': execution_id,
                    'status': 'planning', 
                    'message': 'Initializing sophisticated planning agents',
                    'progress': 10,
                    'hitl_enabled': self.config.execution.enable_hitl
                }
                
                # Clear previous state
                self.task_graph.nodes.clear()
                self.task_graph.graphs.clear()
                self.task_graph.root_graph_id = None
                self.task_graph.overall_project_goal = None
                
                # Run execution with periodic updates - JUPYTER SAFE
                result = _run_async_safely(self._run_async_execution(goal, max_steps))
                
                yield {
                    'execution_id': execution_id,
                    'status': 'completed',
                    'message': 'Execution completed successfully',
                    'progress': 100,
                    'final_output': self._extract_final_result(),
                    'node_count': len(self.task_graph.nodes),
                    'hitl_enabled': self.config.execution.enable_hitl
                }
                
            finally:
                # Restore original HITL setting
                if enable_hitl_override is not None:
                    self.config.execution.enable_hitl = original_hitl_setting
                    if original_node_config:
                        self.node_processor.node_processor_config = original_node_config
                        self.hitl_coordinator.config = original_node_config
            
        except Exception as e:
            yield {
                'execution_id': execution_id,
                'status': 'failed',
                'message': f'Execution failed: {str(e)}',
                'error': str(e),
                'hitl_enabled': self.config.execution.enable_hitl,
                'environment': 'jupyter' if _is_jupyter_environment() else 'python'
            }
    
    def _extract_final_result(self) -> str:
        """Extract final result from the task graph."""
        try:
            # Get the root node from the task graph
            if self.task_graph.root_graph_id:
                root_nodes = self.task_graph.get_nodes_in_graph(self.task_graph.root_graph_id)
                if root_nodes:
                    root_node = root_nodes[0]  # Get the first (root) node
                    if root_node and root_node.result:
                        return str(root_node.result)
                    elif root_node and root_node.output_summary:
                        return root_node.output_summary
            
            return "Task completed using sophisticated agent framework"
        except Exception as e:
            logger.warning(f"Could not extract final result: {e}")
            return "Execution completed (result extraction pending)"
    
    def _save_execution_state(self, execution_id: str, result: Dict[str, Any]):
        """Save execution state for later analysis."""
        try:
            state_dir = Path(".agent_executions")
            state_dir.mkdir(exist_ok=True)
            
            state_file = state_dir / f"{execution_id}.json"
            
            # Add task graph state to result
            if hasattr(self.task_graph, 'to_visualization_dict'):
                result['task_graph_state'] = self.task_graph.to_visualization_dict()
            
            import json
            with open(state_file, 'w') as f:
                json.dump(result, f, indent=2, default=str)
            
            logger.debug(f"Execution state saved to {state_file}")
        except Exception as e:
            logger.warning(f"Failed to save execution state: {e}")
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get comprehensive system information."""
        cache_stats = self.cache_manager.get_stats() if self.cache_manager else None
        error_stats = self.error_handler.get_error_stats() if self.error_handler else None
        
        return {
            "config": {
                "llm_provider": self.config.llm.provider,
                "llm_model": self.config.llm.model,
                "cache_enabled": self.config.cache.enabled,
                "cache_type": self.config.cache.cache_type,
                "max_concurrent_nodes": self.config.execution.max_concurrent_nodes,
                "max_execution_steps": self.config.execution.max_execution_steps,
                "hitl_enabled": self.config.execution.enable_hitl,
                "environment": self.config.environment
            },
            "cache_stats": cache_stats,
            "error_stats": error_stats,
            "graph_stats": {
                "total_nodes": len(self.task_graph.nodes),
                "total_graphs": len(self.task_graph.graphs)
            },
            "framework_available": FRAMEWORK_AVAILABLE
        }
    
    def validate_configuration(self) -> Dict[str, Any]:
        """Validate current configuration and return results."""
        return validate_config(self.config)


# Convenience functions for quick usage
def quick_research(topic: str, enable_hitl: Optional[bool] = None, **kwargs) -> str:
    """Quick research using the sophisticated agent system."""
    if not FRAMEWORK_AVAILABLE:
        raise ImportError("Framework components not available. Please check installation.")
    
    agent = SentientAgent.create(enable_hitl=enable_hitl)
    result = agent.execute(f"Research {topic} and provide a comprehensive summary", **kwargs)
    return result.get('final_output', 'No output generated')


def quick_analysis(data_description: str, enable_hitl: Optional[bool] = None, **kwargs) -> str:
    """Quick analysis using the sophisticated agent system."""
    if not FRAMEWORK_AVAILABLE:
        raise ImportError("Framework components not available. Please check installation.")
    
    agent = SentientAgent.create(enable_hitl=enable_hitl)
    result = agent.execute(f"Analyze {data_description} and provide insights", **kwargs)
    return result.get('final_output', 'No output generated')


def quick_execute(goal: str, enable_hitl: Optional[bool] = None, **kwargs) -> str:
    """Quick execution of any goal using the sophisticated agent system."""
    if not FRAMEWORK_AVAILABLE:
        raise ImportError("Framework components not available. Please check installation.")
    
    agent = SentientAgent.create(enable_hitl=enable_hitl)
    result = agent.execute(goal, **kwargs)
    return result.get('final_output', 'No output generated')


# Backward compatibility aliases
SimpleSentientAgent = SentientAgent  # For existing code 

def _is_jupyter_environment() -> bool:
    """Check if we're running in a Jupyter notebook environment."""
    try:
        # Check for IPython/Jupyter
        from IPython import get_ipython
        return get_ipython() is not None
    except ImportError:
        return False

def _run_async_safely(coro):
    """Run async code safely in both Jupyter and regular Python environments."""
    if _is_jupyter_environment():
        # In Jupyter, use nest_asyncio to allow nested event loops
        try:
            import nest_asyncio
            nest_asyncio.apply()
        except ImportError:
            logger.warning("nest_asyncio not available. Install with: pip install nest_asyncio")
        
        # Try to get the current event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, we need to use a different approach
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, coro)
                    return future.result()
            else:
                return asyncio.run(coro)
        except RuntimeError:
            # No event loop, safe to use asyncio.run
            return asyncio.run(coro)
    else:
        # Regular Python environment
        return asyncio.run(coro) 