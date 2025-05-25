"""
Simplified API that works WITH the existing sophisticated agent system.
This provides an easy entry point while preserving all existing functionality.
"""

from typing import Dict, Any, Optional, Union, Iterator
from pathlib import Path
from datetime import datetime
import uuid

from loguru import logger

try:
    # Import existing framework components (no changes needed)
    from .hierarchical_agent_framework.graph.task_graph import TaskGraph
    from .hierarchical_agent_framework.graph.state_manager import StateManager
    from .hierarchical_agent_framework.graph.execution_engine import ExecutionEngine
    from .hierarchical_agent_framework.node.node_processor import NodeProcessor
    from .hierarchical_agent_framework.context.knowledge_store import KnowledgeStore

    # Import existing configuration system (preserve current approach)
    from .config import load_config, SentientConfig

    FRAMEWORK_AVAILABLE = True
    
except ImportError as e:
    logger.error(f"Framework components not available: {e}")
    FRAMEWORK_AVAILABLE = False


class SimpleSentientAgent:
    """
    Simplified API that wraps the existing sophisticated framework.
    
    This provides an easy entry point for users while preserving all the
    sophisticated agent definitions and registry system that already exists.
    """
    
    def __init__(self, config: Optional['SentientConfig'] = None):
        """Initialize with existing configuration system."""
        if not FRAMEWORK_AVAILABLE:
            raise ImportError("Framework components not available. Please check installation.")
            
        # Use existing config loading if none provided
        self.config = config or load_config()
        
        # Initialize existing framework components (no changes)
        self._initialize_framework()
        
        logger.info("SimpleSentientAgent initialized with existing framework")
    
    @classmethod
    def create(cls, config_path: Optional[Union[str, Path]] = None) -> "SimpleSentientAgent":
        """Create agent using existing configuration system."""
        if not FRAMEWORK_AVAILABLE:
            raise ImportError("Framework components not available. Please check installation.")
            
        if config_path:
            config = SentientConfig.from_yaml(config_path)
        else:
            config = load_config()  # Use existing smart loading
        
        return cls(config)
    
    def execute(self, goal: str, **options) -> Dict[str, Any]:
        """
        Execute a goal using the existing sophisticated agent system.
        
        This method provides a simple interface while leveraging all the
        existing agent definitions (planners, executors, aggregators, etc.)
        """
        start_time = datetime.now()
        execution_id = f"exec_{uuid.uuid4().hex[:8]}"
        
        try:
            logger.info(f"[{execution_id}] Starting execution: {goal[:100]}...")
            
            # Use existing execution engine (no changes to sophisticated system)
            self.execution_engine.initialize_project(root_goal=goal)
            
            # Run execution cycle using existing sophisticated agents
            execution_result = self.execution_engine.run_execution_cycle()
            
            # Extract results from existing framework
            final_output = self._extract_final_result()
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return {
                'execution_id': execution_id,
                'goal': goal,
                'status': 'completed',
                'final_output': final_output,
                'execution_time': execution_time,
                'framework_result': execution_result  # Include full framework result
            }
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"[{execution_id}] Execution failed: {e}")
            
            return {
                'execution_id': execution_id,
                'goal': goal,
                'status': 'failed',
                'error': str(e),
                'execution_time': execution_time
            }
    
    def stream_execution(self, goal: str, **options) -> Iterator[Dict[str, Any]]:
        """Stream execution progress using existing framework."""
        execution_id = f"stream_{uuid.uuid4().hex[:8]}"
        
        try:
            yield {
                'execution_id': execution_id,
                'status': 'initializing',
                'message': f'Starting: {goal[:50]}...',
                'progress': 0
            }
            
            # Initialize using existing system
            self.execution_engine.initialize_project(root_goal=goal)
            
            yield {
                'execution_id': execution_id,
                'status': 'planning', 
                'message': 'Using sophisticated planning agents',
                'progress': 10
            }
            
            # TODO: Integrate with existing execution engine's step-by-step execution
            # For now, run full execution and yield final result
            result = self.execution_engine.run_execution_cycle()
            
            yield {
                'execution_id': execution_id,
                'status': 'completed',
                'message': 'Execution completed',
                'progress': 100,
                'final_output': self._extract_final_result()
            }
            
        except Exception as e:
            yield {
                'execution_id': execution_id,
                'status': 'failed',
                'message': f'Execution failed: {str(e)}',
                'error': str(e)
            }
    
    def _initialize_framework(self):
        """Initialize existing framework components without modification."""
        try:
            # Use existing sophisticated components
            self.task_graph = TaskGraph()
            self.knowledge_store = KnowledgeStore()
            self.state_manager = StateManager(self.task_graph)
            self.node_processor = NodeProcessor()
            
            # Initialize execution engine with existing sophisticated agents
            self.execution_engine = ExecutionEngine(
                task_graph=self.task_graph,
                node_processor=self.node_processor,
                state_manager=self.state_manager,
                knowledge_store=self.knowledge_store
            )
            
            logger.debug("Existing framework components initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize framework: {e}")
            raise
    
    def _extract_final_result(self) -> str:
        """Extract final result from existing framework structures."""
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


# Only define convenience functions if framework is available
if FRAMEWORK_AVAILABLE:
    def quick_research(topic: str, **kwargs) -> str:
        """Quick research using existing sophisticated agents."""
        agent = SimpleSentientAgent.create()
        result = agent.execute(f"Research {topic} and provide a comprehensive summary", **kwargs)
        return result.get('final_output', 'No output generated')

    def quick_analysis(data_description: str, **kwargs) -> str:
        """Quick analysis using existing sophisticated agents."""
        agent = SimpleSentientAgent.create()
        result = agent.execute(f"Analyze {data_description} and provide insights", **kwargs)
        return result.get('final_output', 'No output generated')
else:
    def quick_research(*args, **kwargs):
        raise ImportError("Framework components not available. Please check installation.")
        
    def quick_analysis(*args, **kwargs):
        raise ImportError("Framework components not available. Please check installation.") 