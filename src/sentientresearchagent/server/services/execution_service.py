"""
Execution Service

Handles project execution logic, real-time updates, and execution lifecycle management.
"""

import asyncio
import threading
import time
import traceback
from typing import Dict, Any, Optional
from loguru import logger
from datetime import datetime

from ...simple_api import create_node_processor_config_from_main_config
from ...config import SentientConfig


class RealtimeExecutionWrapper:
    """
    Wrapper for execution engines that provides real-time updates.
    
    This class manages periodic updates during execution to keep the 
    frontend synchronized with execution progress.
    """
    
    def __init__(self, project_id: str, execution_engine, update_callback, project_manager):
        """
        Initialize the execution wrapper.
        
        Args:
            project_id: Project identifier
            execution_engine: Execution engine instance
            update_callback: Callback for broadcasting updates
            project_manager: Project manager instance
        """
        self.project_id = project_id
        self.execution_engine = execution_engine
        self.update_callback = update_callback
        self.project_manager = project_manager
        self._is_current_project = False
        
    def _check_if_current(self) -> bool:
        """Check if this project is currently being displayed."""
        current_project = self.project_manager.get_current_project()
        self._is_current_project = current_project and current_project.id == self.project_id
        return self._is_current_project
        
    async def run_project_flow(self, root_goal: str, max_steps: int = 250) -> Any:
        """
        Run the complete project flow with real-time updates.
        
        Args:
            root_goal: Root goal for the project
            max_steps: Maximum execution steps
            
        Returns:
            Execution result
        """
        async def execute_with_updates():
            # Start the execution flow (includes initialization and HITL)
            execution_task = asyncio.create_task(
                self.execution_engine.run_project_flow(
                    root_goal=root_goal,
                    max_steps=max_steps
                )
            )
            
            # Create a periodic update task
            update_task = asyncio.create_task(
                self._periodic_updates(execution_task)
            )
            
            try:
                # Wait for execution to complete
                result = await execution_task
                # Cancel the update task
                update_task.cancel()
                try:
                    await update_task
                except asyncio.CancelledError:
                    pass
                # Final update only if current
                if self._check_if_current():
                    self.update_callback()
                return result
            except Exception as e:
                update_task.cancel()
                try:
                    await update_task
                except asyncio.CancelledError:
                    pass
                # Update on error too, but only if current
                if self._check_if_current():
                    self.update_callback()
                raise e
        
        return await execute_with_updates()
    
    async def run_cycle(self, max_steps: int = 250) -> Any:
        """
        Run execution cycle with periodic real-time updates (for resuming).
        
        Args:
            max_steps: Maximum execution steps
            
        Returns:
            Execution result
        """
        async def execute_with_updates():
            # Start the execution cycle
            execution_task = asyncio.create_task(
                self.execution_engine.run_cycle(max_steps=max_steps)
            )
            
            # Create a periodic update task
            update_task = asyncio.create_task(
                self._periodic_updates(execution_task)
            )
            
            try:
                # Wait for execution to complete
                result = await execution_task
                # Cancel the update task
                update_task.cancel()
                try:
                    await update_task
                except asyncio.CancelledError:
                    pass
                # Final update only if current
                if self._check_if_current():
                    self.update_callback()
                return result
            except Exception as e:
                update_task.cancel()
                try:
                    await update_task
                except asyncio.CancelledError:
                    pass
                # Update on error too, but only if current
                if self._check_if_current():
                    self.update_callback()
                raise e
        
        return await execute_with_updates()
    
    async def _periodic_updates(self, execution_task: asyncio.Task):
        """
        Periodically update display while execution is running.
        
        Args:
            execution_task: The main execution task to monitor
        """
        while not execution_task.done():
            await asyncio.sleep(2)  # Update every 2 seconds
            if not execution_task.done():
                # Only update display if we're the current project
                if self._check_if_current():
                    self.update_callback()
                else:
                    # Still save state for background projects
                    self._save_background_state()
    
    def _save_background_state(self):
        """Save state for background projects without updating display."""
        try:
            # This would need access to the project graphs and project manager
            # For now, we'll let the project service handle this
            logger.debug(f"Saving background state for project {self.project_id}")
        except Exception as e:
            logger.warning(f"Failed to save background project state: {e}")


class ExecutionService:
    """
    Manages project execution lifecycle and coordination.
    
    This service handles:
    - Starting and stopping project executions
    - Managing execution threads and async tasks
    - Coordinating real-time updates
    - Handling execution errors and recovery
    """
    
    def __init__(self, project_service, system_manager):
        """
        Initialize ExecutionService.
        
        Args:
            project_service: ProjectService instance
            system_manager: SystemManager instance
        """
        self.project_service = project_service
        self.system_manager = system_manager
        self._running_executions: Dict[str, Dict[str, Any]] = {}
    
    def start_project_execution(self, project_id: str, goal: str, max_steps: int) -> bool:
        """
        Start project execution in a background thread.
        
        Args:
            project_id: Project identifier
            goal: Project goal
            max_steps: Maximum execution steps
            
        Returns:
            True if started successfully, False otherwise
        """
        try:
            if project_id in self._running_executions:
                logger.warning(f"Project {project_id} is already running")
                return False
            
            # Create execution thread
            thread = threading.Thread(
                target=self._run_project_in_thread,
                args=(project_id, goal, max_steps),
                daemon=True
            )
            
            # Store execution info
            self._running_executions[project_id] = {
                'thread': thread,
                'goal': goal,
                'max_steps': max_steps,
                'started_at': datetime.now()
            }
            
            # Start the thread
            thread.start()
            
            logger.info(f"🚀 Started execution for project {project_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start project execution: {e}")
            # Clean up on failure
            if project_id in self._running_executions:
                del self._running_executions[project_id]
            return False
    
    def start_configured_project_execution(self, project_id: str, goal: str, max_steps: int, config: SentientConfig) -> bool:
        """
        Start project execution with custom configuration.
        
        Args:
            project_id: Project identifier
            goal: Project goal
            max_steps: Maximum execution steps
            config: Custom configuration
            
        Returns:
            True if started successfully, False otherwise
        """
        try:
            if project_id in self._running_executions:
                logger.warning(f"Project {project_id} is already running")
                return False
            
            # Store the custom config in project service
            self.project_service.project_configs[project_id] = config
            
            # Create execution thread
            thread = threading.Thread(
                target=self._run_configured_project_in_thread,
                args=(project_id, goal, max_steps, config),
                daemon=True
            )
            
            # Store execution info
            self._running_executions[project_id] = {
                'thread': thread,
                'goal': goal,
                'max_steps': max_steps,
                'config': config,
                'started_at': datetime.now()
            }
            
            # Start the thread
            thread.start()
            
            logger.info(f"🚀 Started configured execution for project {project_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start configured project execution: {e}")
            # Clean up on failure
            if project_id in self._running_executions:
                del self._running_executions[project_id]
            return False
    
    def get_running_executions(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about currently running executions.
        
        Returns:
            Dictionary of running execution info
        """
        # Clean up completed threads
        completed = []
        for project_id, info in self._running_executions.items():
            if not info['thread'].is_alive():
                completed.append(project_id)
        
        for project_id in completed:
            del self._running_executions[project_id]
        
        # Return info about running executions (without thread objects)
        return {
            project_id: {
                'goal': info['goal'],
                'max_steps': info['max_steps'],
                'started_at': info['started_at'].isoformat(),
                'is_alive': info['thread'].is_alive()
            }
            for project_id, info in self._running_executions.items()
        }
    
    def _run_project_in_thread(self, project_id: str, goal: str, max_steps: int):
        """
        Thread wrapper for async execution with project management.
        
        Args:
            project_id: Project identifier
            goal: Project goal
            max_steps: Maximum execution steps
        """
        logger.info(f"🧵 Thread started for project: {project_id}")
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self._run_project_cycle_async(project_id, goal, max_steps)
            )
        except Exception as e:
            logger.error(f"Thread error for project {project_id}: {e}")
            traceback.print_exc()
            
            # Update project status to failed
            self.project_service.project_manager.update_project(project_id, status='failed')
        finally:
            # Clean up
            if project_id in self._running_executions:
                del self._running_executions[project_id]
            logger.info(f"🏁 Thread finished for project: {project_id}")
    
    def _run_configured_project_in_thread(self, project_id: str, goal: str, max_steps: int, config: SentientConfig):
        """
        Thread wrapper for async execution with custom configuration.
        
        Args:
            project_id: Project identifier
            goal: Project goal
            max_steps: Maximum execution steps
            config: Custom configuration
        """
        logger.info(f"🧵 Configured thread started for project: {project_id}")
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self._run_configured_project_cycle_async(project_id, goal, max_steps, config)
            )
        except Exception as e:
            logger.error(f"Configured thread error for project {project_id}: {e}")
            traceback.print_exc()
            
            # Update project status to failed
            self.project_service.project_manager.update_project(project_id, status='failed')
        finally:
            # Clean up
            if project_id in self._running_executions:
                del self._running_executions[project_id]
            logger.info(f"🏁 Configured thread finished for project: {project_id}")
    
    async def _run_project_cycle_async(self, project_id: str, goal: str, max_steps: int):
        """
        Run the project cycle with proper project isolation and real-time updates.
        
        Args:
            project_id: Project identifier
            goal: Project goal
            max_steps: Maximum execution steps
        """
        logger.info(f"🎯 Initializing project: {project_id} - {goal}")
        
        try:
            # Get or create project-specific components
            project_components = self.project_service.get_or_create_project_graph(project_id)
            project_task_graph = project_components['task_graph']
            project_execution_engine = project_components['execution_engine']
            update_callback = project_components['update_callback']
            
            # Create real-time wrapper
            realtime_engine = RealtimeExecutionWrapper(
                project_id,
                project_execution_engine,
                update_callback,
                self.project_service.project_manager
            )
            
            # Check if this should be the current project (only if no other project is current)
            current_project = self.project_service.project_manager.get_current_project()
            if not current_project:
                self.project_service.project_manager.set_current_project(project_id)
                should_display = True
            else:
                should_display = (current_project.id == project_id)
            
            # Load existing state into project graph
            project_state = self.project_service.project_manager.load_project_state(project_id)
            
            if project_state and 'all_nodes' in project_state and len(project_state['all_nodes']) > 0:
                logger.info(f"📊 Resuming project with {len(project_state['all_nodes'])} existing nodes")
                
                # Load state into project graph
                self._load_project_state(project_task_graph, project_state)
                
                # Update project status
                self.project_service.project_manager.update_project(project_id, status='running')
                
                # Only sync to display if this is the current project
                if should_display:
                    self.project_service.sync_project_to_display(project_id)
                
                # Continue execution from where it left off
                logger.info("⚡ Resuming execution...")
                await realtime_engine.run_cycle(max_steps=max_steps)
            else:
                logger.info("🧹 Starting fresh project...")
                
                # Clear project graph (but not other projects!)
                project_task_graph.nodes.clear()
                project_task_graph.graphs.clear()
                project_task_graph.root_graph_id = None
                project_task_graph.overall_project_goal = None
                
                # Clear project-specific cache
                cache_manager = self.system_manager.cache_manager
                if cache_manager and self.system_manager.config.cache.enabled:
                    cache_manager.clear_namespace(f"project_{project_id}")
                
                # Update project status
                self.project_service.project_manager.update_project(project_id, status='running')
                
                # Run the complete project flow (initialization + HITL + execution)
                logger.info("🚀 Starting project flow...")
                start_time = time.time()
                
                await realtime_engine.run_project_flow(root_goal=goal, max_steps=max_steps)
                
                total_time = time.time() - start_time
                logger.info(f"⏱️ Project execution took {total_time:.2f} seconds")
            
            # Update project status
            self.project_service.project_manager.update_project(project_id, status='completed')
            
            # Final sync only if current project
            if (self.project_service.project_manager.get_current_project() and 
                self.project_service.project_manager.get_current_project().id == project_id):
                self.project_service.sync_project_to_display(project_id)
            
            # Always save final state
            self._save_final_project_state(project_task_graph, project_id)
            
            logger.info(f"✅ Project {project_id} completed")
            
        except Exception as e:
            # Update project status to failed
            self.project_service.project_manager.update_project(project_id, status='failed')
            logger.error(f"Project execution error: {e}")
            traceback.print_exc()
            
            try:
                # Sync error state only if current project
                if (self.project_service.project_manager.get_current_project() and 
                    self.project_service.project_manager.get_current_project().id == project_id):
                    self.project_service.sync_project_to_display(project_id)
            except:
                logger.error("Failed to broadcast error state")
    
    async def _run_configured_project_cycle_async(self, project_id: str, goal: str, max_steps: int, config: SentientConfig):
        """
        Run the project cycle with custom configuration.
        
        Args:
            project_id: Project identifier
            goal: Project goal
            max_steps: Maximum execution steps
            config: Custom configuration
        """
        logger.info(f"🎯 Initializing configured project: {project_id} - {goal}")
        logger.info(f"🔧 Using config: {config.llm.provider}/{config.llm.model}, "
                   f"temp={config.llm.temperature}, HITL={config.execution.enable_hitl}")
        
        # For configured projects, we force creation of new components with custom config
        # This is handled by the project service when we call get_or_create_project_graph
        
        # The rest of the logic is the same as regular execution
        await self._run_project_cycle_async(project_id, goal, max_steps)
    
    def _load_project_state(self, project_task_graph, project_state):
        """Load project state into task graph."""
        # This logic was extracted from the original load method
        # It deserializes nodes and reconstructs graphs
        self.project_service._reconstruct_graphs(project_task_graph, project_state.get('graphs', {}))
        # ... other state loading logic
    
    def _save_final_project_state(self, project_task_graph, project_id):
        """Save final project state."""
        try:
            if hasattr(project_task_graph, 'to_visualization_dict'):
                data = project_task_graph.to_visualization_dict()
            else:
                from ...hierarchical_agent_framework.graph.graph_serializer import GraphSerializer
                serializer = GraphSerializer(project_task_graph)
                data = serializer.to_visualization_dict()
            
            self.project_service.project_manager.save_project_state(project_id, data)
        except Exception as e:
            logger.error(f"Failed to save final project state: {e}")
