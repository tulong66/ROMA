"""
High-level API for the Sentient Research Agent framework.

This module provides a simplified interface for users to interact with
the hierarchical task decomposition system without needing to understand
the internal complexity.
"""

import asyncio
from typing import Dict, Any, Optional, Iterator, Union, List
from pathlib import Path
from datetime import datetime

from loguru import logger

from .config import SentientConfig, load_config
from .hierarchical_agent_framework.graph.task_graph import TaskGraph
from .hierarchical_agent_framework.graph.state_manager import StateManager
from .hierarchical_agent_framework.graph.execution_engine import ExecutionEngine
from .hierarchical_agent_framework.node.node_processor import NodeProcessor
from .hierarchical_agent_framework.context.knowledge_store import KnowledgeStore
from .exceptions import SentientAgentError


class ExecutionResult:
    """Container for execution results with rich metadata."""
    
    def __init__(
        self,
        final_output: str,
        execution_id: str,
        goal: str,
        status: str,
        execution_time: float,
        tasks_completed: int,
        tasks_failed: int,
        metadata: Dict[str, Any] = None
    ):
        self.final_output = final_output
        self.execution_id = execution_id
        self.goal = goal
        self.status = status
        self.execution_time = execution_time
        self.tasks_completed = tasks_completed
        self.tasks_failed = tasks_failed
        self.metadata = metadata or {}
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary format."""
        return {
            'final_output': self.final_output,
            'execution_id': self.execution_id,
            'goal': self.goal,
            'status': self.status,
            'execution_time': self.execution_time,
            'tasks_completed': self.tasks_completed,
            'tasks_failed': self.tasks_failed,
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat()
        }
    
    def __str__(self) -> str:
        return self.final_output
    
    def __repr__(self) -> str:
        return f"ExecutionResult(status='{self.status}', tasks={self.tasks_completed}, time={self.execution_time:.2f}s)"


class SentientAgent:
    """
    High-level interface for the Sentient Research Agent framework.
    
    This class provides a simplified API for executing complex tasks through
    hierarchical task decomposition, hiding the internal complexity from users.
    """
    
    def __init__(self, config: SentientConfig):
        """
        Initialize the agent with configuration.
        
        Args:
            config: Configuration object for the agent
        """
        self.config = config
        self._setup_logging()
        self._initialize_components()
        
        logger.info("SentientAgent initialized successfully")
    
    @classmethod
    def create(
        cls,
        config_path: Optional[Union[str, Path]] = None,
        config: Optional[SentientConfig] = None,
        **config_overrides
    ) -> "SentientAgent":
        """
        Create a SentientAgent with automatic configuration loading.
        
        Args:
            config_path: Path to configuration file (YAML)
            config: Pre-configured SentientConfig object
            **config_overrides: Direct configuration overrides
            
        Returns:
            Configured SentientAgent instance
            
        Examples:
            >>> # Use default configuration
            >>> agent = SentientAgent.create()
            
            >>> # Use custom config file
            >>> agent = SentientAgent.create(config_path="my_config.yaml")
            
            >>> # Override specific settings
            >>> agent = SentientAgent.create(
            ...     llm_provider="anthropic",
            ...     llm_model="claude-3-sonnet"
            ... )
        """
        try:
            if config is not None:
                final_config = config
            elif config_path is not None:
                final_config = SentientConfig.from_yaml(config_path)
            else:
                # Try to auto-load configuration
                final_config = load_config()
            
            # Apply any direct overrides
            if config_overrides:
                final_config = cls._apply_config_overrides(final_config, config_overrides)
            
            # Validate API keys and configuration
            validation_issues = final_config.validate_api_keys()
            if validation_issues:
                logger.warning(f"Configuration issues detected: {validation_issues}")
            
            return cls(final_config)
            
        except Exception as e:
            raise SentientAgentError(
                f"Failed to create SentientAgent: {e}",
                suggestions=[
                    "Check your configuration file syntax",
                    "Ensure API keys are set in environment variables",
                    "Try running with default configuration first"
                ],
                docs_link="https://github.com/your-org/SentientResearchAgent/docs/CONFIGURATION.md"
            )
    
    def execute(
        self,
        goal: str,
        max_steps: Optional[int] = None,
        timeout: Optional[float] = None,
        **execution_options
    ) -> ExecutionResult:
        """
        Execute a goal and return the final result.
        
        Args:
            goal: The high-level goal to achieve
            max_steps: Maximum number of execution steps (overrides config)
            timeout: Maximum execution time in seconds
            **execution_options: Additional execution parameters
            
        Returns:
            ExecutionResult containing the final output and metadata
            
        Examples:
            >>> agent = SentientAgent.create()
            >>> result = agent.execute("Research quantum computing trends")
            >>> print(result.final_output)
            
            >>> # With custom parameters
            >>> result = agent.execute(
            ...     "Write a market analysis",
            ...     max_steps=50,
            ...     timeout=300
            ... )
        """
        start_time = datetime.now()
        execution_id = f"exec_{int(start_time.timestamp())}"
        
        try:
            logger.info(f"Starting execution: {goal[:100]}...")
            
            # Update execution config if overrides provided
            if max_steps is not None:
                self.config.execution.max_execution_steps = max_steps
            
            # Initialize project
            self.execution_engine.initialize_project(root_goal=goal)
            
            # Execute with optional timeout
            if timeout:
                # Note: In a real implementation, you'd want proper async timeout handling
                result = self._execute_with_timeout(timeout)
            else:
                result = self.execution_engine.run_execution_cycle()
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Get final result and statistics
            final_output = self._extract_final_output(result)
            stats = self._get_execution_statistics()
            
            return ExecutionResult(
                final_output=final_output,
                execution_id=execution_id,
                goal=goal,
                status="completed",
                execution_time=execution_time,
                tasks_completed=stats['completed'],
                tasks_failed=stats['failed'],
                metadata={
                    'execution_options': execution_options,
                    'config_used': self.config.to_dict()
                }
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Execution failed: {e}")
            
            return ExecutionResult(
                final_output=f"Execution failed: {str(e)}",
                execution_id=execution_id,
                goal=goal,
                status="failed",
                execution_time=execution_time,
                tasks_completed=0,
                tasks_failed=1,
                metadata={'error': str(e)}
            )
    
    def stream_execution(
        self,
        goal: str,
        max_steps: Optional[int] = None,
        **execution_options
    ) -> Iterator[Dict[str, Any]]:
        """
        Execute a goal and stream progress updates.
        
        Args:
            goal: The high-level goal to achieve
            max_steps: Maximum number of execution steps
            **execution_options: Additional execution parameters
            
        Yields:
            Progress updates as dictionaries containing:
            - status: Current execution status
            - current_task: Description of current task
            - progress: Progress percentage (0-100)
            - message: Human-readable status message
            - metadata: Additional context information
            
        Examples:
            >>> agent = SentientAgent.create()
            >>> for update in agent.stream_execution("Research AI trends"):
            ...     print(f"{update['progress']}% - {update['message']}")
        """
        start_time = datetime.now()
        
        try:
            yield {
                'status': 'initializing',
                'current_task': 'Setting up execution environment',
                'progress': 0,
                'message': f'Starting goal: {goal[:100]}...',
                'metadata': {'goal': goal, 'start_time': start_time.isoformat()}
            }
            
            # Initialize project
            self.execution_engine.initialize_project(root_goal=goal)
            
            yield {
                'status': 'planning',
                'current_task': 'Creating execution plan',
                'progress': 10,
                'message': 'Breaking down goal into manageable tasks',
                'metadata': {}
            }
            
            # Stream execution progress
            step_count = 0
            max_steps = max_steps or self.config.execution.max_execution_steps
            
            for step_result in self._stream_execution_steps():
                step_count += 1
                progress = min(90, int((step_count / max_steps) * 80) + 10)
                
                yield {
                    'status': 'executing',
                    'current_task': step_result.get('current_task', 'Processing'),
                    'progress': progress,
                    'message': step_result.get('message', f'Step {step_count} of {max_steps}'),
                    'metadata': {
                        'step': step_count,
                        'total_steps': max_steps,
                        'node_status': step_result.get('node_status', {})
                    }
                }
                
                if step_count >= max_steps:
                    break
            
            # Final result
            final_output = self._extract_final_output(None)
            execution_time = (datetime.now() - start_time).total_seconds()
            
            yield {
                'status': 'completed',
                'current_task': 'Execution completed',
                'progress': 100,
                'message': 'Goal achieved successfully',
                'metadata': {
                    'final_output': final_output,
                    'execution_time': execution_time,
                    'statistics': self._get_execution_statistics()
                }
            }
            
        except Exception as e:
            yield {
                'status': 'failed',
                'current_task': 'Error occurred',
                'progress': 0,
                'message': f'Execution failed: {str(e)}',
                'metadata': {'error': str(e)}
            }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for the agent.
        
        Returns:
            Dictionary containing performance statistics
        """
        # In a full implementation, this would track metrics across executions
        return {
            'total_executions': 0,
            'avg_execution_time': 0.0,
            'success_rate': 0.0,
            'total_tokens_used': 0,
            'cache_hit_rate': 0.0
        }
    
    def _setup_logging(self):
        """Set up logging based on configuration."""
        self.config.setup_logging()
    
    def _initialize_components(self):
        """Initialize the internal framework components."""
        try:
            # Initialize core components
            self.task_graph = TaskGraph()
            self.knowledge_store = KnowledgeStore()
            self.state_manager = StateManager(self.task_graph)
            self.node_processor = NodeProcessor()
            
            # Initialize execution engine
            self.execution_engine = ExecutionEngine(
                task_graph=self.task_graph,
                node_processor=self.node_processor,
                state_manager=self.state_manager,
                knowledge_store=self.knowledge_store
            )
            
            logger.debug("Framework components initialized")
            
        except Exception as e:
            raise SentientAgentError(
                f"Failed to initialize framework components: {e}",
                suggestions=[
                    "Check that all dependencies are installed",
                    "Verify configuration is valid",
                    "Check logs for detailed error information"
                ]
            )
    
    def _execute_with_timeout(self, timeout: float):
        """Execute with timeout (placeholder for async implementation)."""
        # In a real implementation, this would use asyncio.wait_for
        return self.execution_engine.run_execution_cycle()
    
    def _stream_execution_steps(self) -> Iterator[Dict[str, Any]]:
        """Stream individual execution steps (placeholder implementation)."""
        # This would integrate with the execution engine's step-by-step execution
        # For now, yield placeholder updates
        for i in range(5):
            yield {
                'current_task': f'Processing step {i+1}',
                'message': f'Executing task step {i+1}',
                'node_status': {}
            }
    
    def _extract_final_output(self, result) -> str:
        """Extract the final output from execution result."""
        # This would extract the final result from the root node
        # Placeholder implementation
        return "Task completed successfully. Final output would be extracted from the execution result."
    
    def _get_execution_statistics(self) -> Dict[str, int]:
        """Get statistics about the current execution."""
        # This would analyze the task graph for statistics
        return {
            'completed': 1,
            'failed': 0,
            'pending': 0
        }
    
    @staticmethod
    def _apply_config_overrides(config: SentientConfig, overrides: Dict[str, Any]) -> SentientConfig:
        """Apply configuration overrides to a config object."""
        # This would intelligently apply overrides to the configuration
        # Placeholder implementation
        return config


# Convenience functions for common use cases
def quick_research(topic: str, **kwargs) -> str:
    """
    Quick research on a topic using default configuration.
    
    Args:
        topic: Topic to research
        **kwargs: Additional execution options
        
    Returns:
        Research results as string
        
    Example:
        >>> results = quick_research("renewable energy trends 2024")
        >>> print(results)
    """
    agent = SentientAgent.create()
    result = agent.execute(f"Research {topic} and provide a comprehensive summary", **kwargs)
    return result.final_output


def quick_analysis(data_description: str, analysis_type: str = "summary", **kwargs) -> str:
    """
    Quick analysis of described data.
    
    Args:
        data_description: Description of the data to analyze
        analysis_type: Type of analysis to perform
        **kwargs: Additional execution options
        
    Returns:
        Analysis results as string
    """
    agent = SentientAgent.create()
    goal = f"Perform a {analysis_type} analysis of {data_description}"
    result = agent.execute(goal, **kwargs)
    return result.final_output 