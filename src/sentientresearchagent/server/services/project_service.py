"""
Project Service

Handles project management logic including project graphs, state management,
and synchronization with the display.
"""

from typing import Dict, Any, Optional, Callable, List
import traceback
from loguru import logger
from datetime import datetime
import json
import os
from pathlib import Path

from ...project_manager import ProjectManager
from ...simple_api import create_node_processor_config_from_main_config
from ...hierarchical_agent_framework.graph.task_graph import TaskGraph
from ...hierarchical_agent_framework.graph.state_manager import StateManager
from ...hierarchical_agent_framework.graph.execution_engine import ExecutionEngine
from ...hierarchical_agent_framework.node.node_processor import NodeProcessor
from ...hierarchical_agent_framework.node.hitl_coordinator import HITLCoordinator
from ...hierarchical_agent_framework.node.task_node import TaskNode
from ...hierarchical_agent_framework.types import TaskStatus, TaskType, NodeType


class ProjectService:
    """
    Manages project lifecycle, state, and synchronization.
    
    This service handles:
    - Project graph creation and management
    - State synchronization between projects and display
    - Project configuration management
    - Real-time updates and callbacks
    """
    
    def __init__(self, system_manager, broadcast_callback: Optional[Callable] = None):
        """
        Initialize ProjectService.
        
        Args:
            system_manager: SystemManager instance
            broadcast_callback: Optional callback for broadcasting updates
        """
        self.system_manager = system_manager
        self.broadcast_callback = broadcast_callback
        self.project_manager = ProjectManager()
        
        # Store project-specific components
        self.project_graphs: Dict[str, Dict[str, Any]] = {}
        self.project_configs: Dict[str, Any] = {}
        
        # Create results storage directory
        self.results_dir = Path("project_results")
        self.results_dir.mkdir(exist_ok=True)
        
        logger.info("✅ ProjectService initialized")
        
    def get_all_projects(self) -> Dict[str, Any]:
        """
        Get all projects with their metadata.
        
        Returns:
            Dictionary containing projects list and current project ID
        """
        projects = self.project_manager.get_all_projects()
        current_project_id = self.project_manager.get_current_project_id()
        
        # Convert projects to dictionaries and add metadata
        project_dicts = []
        for project in projects:
            project_dict = project.to_dict()
            
            # Add completion metadata if available
            try:
                results_file = self.results_dir / f"{project.id}_results.json"
                if results_file.exists():
                    with open(results_file, 'r') as f:
                        saved_results = json.load(f)
                        project_dict['has_saved_results'] = True
                        project_dict['last_saved'] = saved_results.get('saved_at')
                        project_dict['completion_status'] = saved_results.get('metadata', {}).get('completion_status')
                else:
                    project_dict['has_saved_results'] = False
            except Exception as e:
                logger.warning(f"Failed to check saved results for project {project.id}: {e}")
                project_dict['has_saved_results'] = False
            
            project_dicts.append(project_dict)
        
        return {
            "projects": project_dicts,
            "current_project_id": current_project_id
        }
    
    def create_project(self, goal: str, max_steps: int, custom_config: Optional[Any] = None) -> Dict[str, Any]:
        """
        Create a new project.
        
        Args:
            goal: Project goal description
            max_steps: Maximum execution steps
            custom_config: Optional custom configuration
            
        Returns:
            Dictionary containing project info
        """
        project = self.project_manager.create_project(goal, max_steps)
        
        # Store custom config if provided
        if custom_config:
            self.project_configs[project.id] = custom_config
            logger.info(f"✅ Project {project.id} created with custom configuration")
        else:
            logger.info(f"✅ Project {project.id} created with default configuration")
        
        return project.to_dict()
    
    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific project and its state.
        
        Args:
            project_id: Project identifier
            
        Returns:
            Dictionary containing project and state info, or None if not found
        """
        project = self.project_manager.get_project(project_id)
        if not project:
            return None
        
        # Load project state if it exists
        project_state = self.project_manager.load_project_state(project_id)
        
        # Check for saved results
        project_dict = project.to_dict()
        try:
            results_file = self.results_dir / f"{project_id}_results.json"
            if results_file.exists():
                project_dict['has_saved_results'] = True
                with open(results_file, 'r') as f:
                    saved_results = json.load(f)
                    project_dict['last_saved'] = saved_results.get('saved_at')
                    project_dict['completion_status'] = saved_results.get('metadata', {}).get('completion_status')
            else:
                project_dict['has_saved_results'] = False
        except Exception as e:
            logger.warning(f"Failed to check saved results for project {project_id}: {e}")
            project_dict['has_saved_results'] = False
        
        return {
            "project": project_dict,
            "state": project_state
        }
    
    def switch_project(self, project_id: str) -> bool:
        """
        Switch to a different project.
        
        Args:
            project_id: Project identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Save current project state if there is one
            current_project_id = self.project_manager.get_current_project_id()
            if current_project_id and current_project_id != project_id:
                self._auto_save_current_project()
            
            # Switch to new project
            success = self.project_manager.switch_project(project_id)
            if success:
                # Load saved results if available
                self._auto_load_project_results(project_id)
                logger.info(f"✅ Switched to project {project_id}")
            
            return success
        except Exception as e:
            logger.error(f"Failed to switch to project {project_id}: {e}")
            return False
    
    def delete_project(self, project_id: str) -> bool:
        """
        Delete a project and its saved results.
        
        Args:
            project_id: Project identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Delete saved results
            results_file = self.results_dir / f"{project_id}_results.json"
            if results_file.exists():
                results_file.unlink()
                logger.info(f"🗑️ Deleted saved results for project {project_id}")
            
            # Remove custom config
            if project_id in self.project_configs:
                del self.project_configs[project_id]
            
            # Delete project
            success = self.project_manager.delete_project(project_id)
            if success:
                logger.info(f"🗑️ Deleted project {project_id}")
            
            return success
        except Exception as e:
            logger.error(f"Failed to delete project {project_id}: {e}")
            return False
    
    def get_or_create_project_graph(self, project_id: str) -> Dict[str, Any]:
        """
        Get or create a project-specific task graph and execution engine.
        
        Args:
            project_id: Project identifier
            
        Returns:
            Dictionary containing project-specific components
        """
        if project_id not in self.project_graphs:
            # Check if we have a custom config for this project
            custom_config = self.project_configs.get(project_id, self.system_manager.config)
            
            # Create project-specific components
            project_task_graph = TaskGraph()
            project_state_manager = StateManager(project_task_graph)
            
            # Use the custom config (or default if no custom config)
            node_processor_config = create_node_processor_config_from_main_config(custom_config)
            
            project_hitl_coordinator = HITLCoordinator(config=node_processor_config)
            
            # Create update callback for real-time sync
            update_callback = self._create_project_update_callback(project_id)
            
            # Get the current profile's blueprint from SystemManager
            current_profile = self.system_manager.get_current_profile()
            current_blueprint = None
            if current_profile:
                try:
                    from ...hierarchical_agent_framework.agent_configs.profile_loader import ProfileLoader
                    profile_loader = ProfileLoader()
                    current_blueprint = profile_loader.load_profile(current_profile)
                    logger.info(f"🎯 Using blueprint '{current_blueprint.name}' for project {project_id}")
                except Exception as e:
                    logger.warning(f"⚠️  Failed to load blueprint for profile '{current_profile}': {e}")

            project_node_processor = NodeProcessor(
                task_graph=project_task_graph,
                knowledge_store=self.system_manager.knowledge_store,
                config=custom_config,
                node_processor_config=node_processor_config,
                agent_blueprint=current_blueprint
            )
            
            project_execution_engine = ExecutionEngine(
                task_graph=project_task_graph,
                state_manager=project_state_manager,
                knowledge_store=self.system_manager.knowledge_store,
                hitl_coordinator=project_hitl_coordinator,
                config=custom_config,
                node_processor=project_node_processor
            )
            
            # Store the project-specific components
            self.project_graphs[project_id] = {
                'task_graph': project_task_graph,
                'state_manager': project_state_manager,
                'execution_engine': project_execution_engine,
                'node_processor': project_node_processor,
                'hitl_coordinator': project_hitl_coordinator,
                'update_callback': update_callback,
                'config': custom_config
            }
            
            config_type = "custom" if project_id in self.project_configs else "default"
            logger.info(f"✅ Created execution environment for project {project_id} "
                       f"({config_type} config, HITL: {'enabled' if custom_config.execution.enable_hitl else 'disabled'})")
        
        return self.project_graphs[project_id]
    
    def sync_project_to_display(self, project_id: str) -> bool:
        """
        Sync a project's current state to the display graph and broadcast.
        
        Args:
            project_id: Project identifier to sync
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if project_id not in self.project_graphs:
                return False
                
            project_task_graph = self.project_graphs[project_id]['task_graph']
            
            # Ensure display graph is valid
            display_graph = self.system_manager.task_graph
            if not hasattr(display_graph, 'nodes') or not hasattr(display_graph, 'graphs'):
                logger.warning("Recreating corrupted display graph")
                self.system_manager.task_graph = TaskGraph()
                display_graph = self.system_manager.task_graph
            
            # Ensure the attributes are dictionaries
            if not isinstance(display_graph.nodes, dict):
                display_graph.nodes = {}
            if not isinstance(display_graph.graphs, dict):
                display_graph.graphs = {}
            
            # Copy project state to live display graph
            display_graph.nodes.clear()
            display_graph.nodes.update(project_task_graph.nodes)
            display_graph.graphs.clear()
            display_graph.graphs.update(project_task_graph.graphs)
            display_graph.overall_project_goal = project_task_graph.overall_project_goal
            display_graph.root_graph_id = project_task_graph.root_graph_id
            
            # Broadcast the update
            if self.broadcast_callback:
                self.broadcast_callback()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to sync project {project_id} to display: {e}")
            traceback.print_exc()
            return False
    
    def load_project_into_graph(self, project_id: str) -> bool:
        """
        Load a project's state into its task graph for display.
        
        Args:
            project_id: Project identifier to load
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get or create project-specific graph
            project_components = self.get_or_create_project_graph(project_id)
            project_task_graph = project_components['task_graph']
            
            # Load saved state into the project's task graph
            project_state = self.project_manager.load_project_state(project_id)
            project = self.project_manager.get_project(project_id)
            
            if project_state:
                # Clear and reload the project's task graph
                project_task_graph.nodes.clear()
                project_task_graph.graphs.clear()
                project_task_graph.root_graph_id = None
                project_task_graph.overall_project_goal = None
                
                if 'all_nodes' in project_state:
                    # Load nodes by deserializing dictionaries back to TaskNode objects
                    for node_id, node_data in project_state['all_nodes'].items():
                        try:
                            # Convert datetime strings back to datetime objects if needed
                            self._deserialize_node_timestamps(node_data)
                            self._deserialize_node_enums(node_data)
                            
                            # Create TaskNode object from dictionary
                            task_node = TaskNode(**node_data)
                            project_task_graph.nodes[node_id] = task_node
                        except Exception as e:
                            logger.warning(f"Failed to deserialize node {node_id}: {e}")
                            continue
                
                # Properly reconstruct graphs
                if 'graphs' in project_state:
                    self._reconstruct_graphs(project_task_graph, project_state['graphs'])
                
                if 'overall_project_goal' in project_state:
                    project_task_graph.overall_project_goal = project_state['overall_project_goal']
                elif project:
                    project_task_graph.overall_project_goal = project.goal
                    
                if 'root_graph_id' in project_state:
                    project_task_graph.root_graph_id = project_state['root_graph_id']
            
            elif project:
                # No saved state, just set the goal
                project_task_graph.overall_project_goal = project.goal
            
            # Sync to display
            self.sync_project_to_display(project_id)
            
            logger.info(f"✅ Loaded project {project_id}: {len(project_task_graph.nodes)} nodes")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load project {project_id}: {e}")
            traceback.print_exc()
            return False
    
    def save_current_project_state(self):
        """Save the current live graph state to the current project."""
        current_project = self.project_manager.get_current_project()
        if current_project:
            try:
                # Use the proper serialization method
                display_graph = self.system_manager.task_graph
                if hasattr(display_graph, 'to_visualization_dict'):
                    data = display_graph.to_visualization_dict()
                else:
                    # Fallback: Import and use GraphSerializer directly
                    from ...hierarchical_agent_framework.graph.graph_serializer import GraphSerializer
                    serializer = GraphSerializer(display_graph)
                    data = serializer.to_visualization_dict()
                
                self.project_manager.save_project_state(current_project.id, data)
                
                # Also update the project-specific graph if it exists
                if current_project.id in self.project_graphs:
                    project_task_graph = self.project_graphs[current_project.id]['task_graph']
                    project_task_graph.nodes.clear()
                    project_task_graph.nodes.update(display_graph.nodes)
                    project_task_graph.graphs.clear()
                    project_task_graph.graphs.update(display_graph.graphs)
                    project_task_graph.overall_project_goal = display_graph.overall_project_goal
                    project_task_graph.root_graph_id = display_graph.root_graph_id
                
                logger.info(f"💾 Saved state for project {current_project.id}")
            except Exception as e:
                logger.error(f"Failed to save current project state: {e}")
                traceback.print_exc()
    
    def get_project_config(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the configuration used for a specific project.
        
        Args:
            project_id: Project identifier
            
        Returns:
            Configuration dictionary or None if not found
        """
        if project_id not in self.project_configs:
            return None
        
        config = self.project_configs[project_id]
        
        # Convert config to dictionary for JSON response
        return {
            "llm": {
                "provider": config.llm.provider,
                "model": config.llm.model,
                "temperature": config.llm.temperature,
                "max_tokens": getattr(config.llm, 'max_tokens', None),
                "timeout": config.llm.timeout,
                "max_retries": config.llm.max_retries
            },
            "execution": {
                "max_concurrent_nodes": config.execution.max_concurrent_nodes,
                "max_execution_steps": config.execution.max_execution_steps,
                "max_recursion_depth": getattr(config.execution, 'max_recursion_depth', 5),
                "task_timeout_seconds": getattr(config.execution, 'task_timeout_seconds', 300),
                "enable_hitl": config.execution.enable_hitl,
                "hitl_root_plan_only": config.execution.hitl_root_plan_only,
                "hitl_timeout_seconds": config.execution.hitl_timeout_seconds,
                "hitl_after_plan_generation": config.execution.hitl_after_plan_generation,
                "hitl_after_modified_plan": config.execution.hitl_after_modified_plan,
                "hitl_after_atomizer": config.execution.hitl_after_atomizer,
                "hitl_before_execute": config.execution.hitl_before_execute
            },
            "cache": {
                "enabled": config.cache.enabled,
                "ttl_seconds": config.cache.ttl_seconds,
                "max_size": config.cache.max_size,
                "cache_type": config.cache.cache_type
            }
        }
    
    def _create_project_update_callback(self, project_id: str) -> Callable:
        """Create a callback function that syncs project updates to display."""
        def update_callback():
            # Only sync if this is the current project
            current_project = self.project_manager.get_current_project()
            if current_project and current_project.id == project_id:
                self.sync_project_to_display(project_id)
            # If not current project, just save the state without syncing to display
            else:
                try:
                    project_components = self.project_graphs.get(project_id)
                    if project_components:
                        project_task_graph = project_components['task_graph']
                        if hasattr(project_task_graph, 'to_visualization_dict'):
                            data = project_task_graph.to_visualization_dict()
                        else:
                            from ...hierarchical_agent_framework.graph.graph_serializer import GraphSerializer
                            serializer = GraphSerializer(project_task_graph)
                            data = serializer.to_visualization_dict()
                        self.project_manager.save_project_state(project_id, data)
                except Exception as e:
                    logger.warning(f"Failed to save state for background project {project_id}: {e}")
        
        return update_callback
    
    def _clear_display_graph(self):
        """Clear the display graph."""
        display_graph = self.system_manager.task_graph
        display_graph.nodes.clear()
        display_graph.graphs.clear()
        display_graph.root_graph_id = None
        display_graph.overall_project_goal = None
    
    def _deserialize_node_timestamps(self, node_data: Dict[str, Any]):
        """Convert datetime strings back to datetime objects."""
        datetime_fields = ['timestamp_created', 'timestamp_updated', 'timestamp_completed']
        for field in datetime_fields:
            if isinstance(node_data.get(field), str):
                node_data[field] = datetime.fromisoformat(node_data[field])
    
    def _deserialize_node_enums(self, node_data: Dict[str, Any]):
        """Fix status and type enums if they're strings."""
        if 'status' in node_data and isinstance(node_data['status'], str):
            node_data['status'] = TaskStatus(node_data['status'])
        
        if 'task_type' in node_data and isinstance(node_data['task_type'], str):
            node_data['task_type'] = TaskType(node_data['task_type'])
        
        if 'node_type' in node_data and isinstance(node_data['node_type'], str):
            node_data['node_type'] = NodeType(node_data['node_type'])
    
    def _reconstruct_graphs(self, project_task_graph: TaskGraph, graphs_data: Dict[str, Any]):
        """Reconstruct NetworkX graphs from serialized data."""
        import networkx as nx
        
        project_task_graph.graphs.clear()
        
        for graph_id, graph_data in graphs_data.items():
            try:
                # Create a new DiGraph
                new_graph = nx.DiGraph()
                
                # Add nodes
                if 'nodes' in graph_data:
                    new_graph.add_nodes_from(graph_data['nodes'])
                
                # Add edges
                if 'edges' in graph_data:
                    for edge in graph_data['edges']:
                        if isinstance(edge, dict) and 'source' in edge and 'target' in edge:
                            new_graph.add_edge(edge['source'], edge['target'])
                        elif isinstance(edge, (list, tuple)) and len(edge) == 2:
                            new_graph.add_edge(edge[0], edge[1])
                
                project_task_graph.graphs[graph_id] = new_graph
            except Exception as e:
                logger.warning(f"Failed to reconstruct graph {graph_id}: {e}")

    def _check_system_readiness_for_execution(self) -> bool:
        """
        Check if the system is ready for project execution.
        
        Returns:
            True if system is ready, False otherwise
        """
        # Check if WebSocket HITL is ready (if HITL is enabled)
        if self.system_manager.config.execution.enable_hitl:
            if not self.system_manager.is_websocket_hitl_ready():
                logger.warning("⚠️ WebSocket HITL not ready - execution may auto-approve HITL requests")
                return False
        
        return True

    def start_project_execution(self, project_id: str) -> Dict[str, Any]:
        """
        Start execution for a project.
        
        Args:
            project_id: ID of the project to start
            
        Returns:
            Dictionary containing execution status
        """
        try:
            # Check system readiness
            if not self._check_system_readiness_for_execution():
                logger.warning("🚨 System not fully ready for execution, but proceeding...")
                # Don't block execution, just warn
            
            # Load the project if not already loaded
            if not self.load_project_into_graph(project_id):
                return {
                    "success": False,
                    "error": f"Failed to load project {project_id}"
                }
            
            # Switch to this project
            if not self.switch_project(project_id):
                return {
                    "success": False,
                    "error": f"Failed to switch to project {project_id}"
                }
            
            # Start execution using the execution service
            execution_result = self.execution_service.start_execution()
            
            return {
                "success": True,
                "project_id": project_id,
                "execution_status": execution_result
            }
            
        except Exception as e:
            logger.error(f"Failed to start project execution for {project_id}: {e}")
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }

    def save_project_results(self, project_id: str, results_package: Dict[str, Any]) -> bool:
        """
        Save project results to persistent storage.
        
        Args:
            project_id: Project identifier
            results_package: Complete results package to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            results_file = self.results_dir / f"{project_id}_results.json"
            
            # Add save metadata
            results_package['save_metadata'] = {
                'saved_at': datetime.now().isoformat(),
                'version': '1.0',
                'project_id': project_id
            }
            
            # Write to file
            with open(results_file, 'w') as f:
                json.dump(results_package, f, indent=2, default=str)
            
            logger.info(f"💾 Saved results for project {project_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save results for project {project_id}: {e}")
            return False
    
    def load_project_results(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Load saved project results from persistent storage.
        
        Args:
            project_id: Project identifier
            
        Returns:
            Results package if found, None otherwise
        """
        try:
            results_file = self.results_dir / f"{project_id}_results.json"
            
            if not results_file.exists():
                return None
            
            with open(results_file, 'r') as f:
                results_package = json.load(f)
            
            logger.info(f"📂 Loaded saved results for project {project_id}")
            return results_package
            
        except Exception as e:
            logger.error(f"Failed to load results for project {project_id}: {e}")
            return None
    
    def _auto_save_current_project(self):
        """
        Automatically save the current project's results.
        """
        try:
            current_project_id = self.project_manager.get_current_project_id()
            if not current_project_id:
                return
            
            # Get current graph data
            graph_data = {}
            if hasattr(self.system_manager, 'task_graph') and self.system_manager.task_graph:
                if hasattr(self.system_manager.task_graph, 'to_visualization_dict'):
                    graph_data = self.system_manager.task_graph.to_visualization_dict()
            
            # Only save if there's meaningful data
            if graph_data.get('all_nodes'):
                project_data = self.get_project(current_project_id)
                if project_data:
                    results_package = {
                        "project": project_data['project'],
                        "saved_at": datetime.now().isoformat(),
                        "graph_data": graph_data,
                        "auto_saved": True,
                        "metadata": {
                            "total_nodes": len(graph_data.get('all_nodes', {})),
                            "project_goal": graph_data.get('overall_project_goal'),
                            "completion_status": self._get_completion_status(graph_data.get('all_nodes', {}))
                        }
                    }
                    
                    self.save_project_results(current_project_id, results_package)
                    logger.info(f"🔄 Auto-saved project {current_project_id}")
        
        except Exception as e:
            logger.warning(f"Failed to auto-save current project: {e}")
    
    def _auto_load_project_results(self, project_id: str):
        """
        Automatically load project results when switching projects.
        """
        try:
            results_package = self.load_project_results(project_id)
            if results_package and results_package.get('graph_data'):
                # Restore graph data to system manager
                if hasattr(self.system_manager, 'task_graph') and self.system_manager.task_graph:
                    # This would need to be implemented based on your graph restoration logic
                    logger.info(f"🔄 Auto-loaded results for project {project_id}")
        
        except Exception as e:
            logger.warning(f"Failed to auto-load project results for {project_id}: {e}")
    
    def _get_completion_status(self, nodes: Dict[str, Any]) -> str:
        """
        Determine project completion status from nodes.
        
        Args:
            nodes: Dictionary of task nodes
            
        Returns:
            Completion status string
        """
        if not nodes:
            return "no_nodes"
        
        total_nodes = len(nodes)
        completed_nodes = sum(1 for node in nodes.values() if node.get('status') == 'DONE')
        failed_nodes = sum(1 for node in nodes.values() if node.get('status') == 'FAILED')
        running_nodes = sum(1 for node in nodes.values() if node.get('status') in ['RUNNING', 'READY'])
        
        if completed_nodes == total_nodes:
            return "completed"
        elif failed_nodes > 0 and running_nodes == 0:
            return "failed"
        elif running_nodes > 0:
            return "running"
        else:
            return "in_progress"
    
    def get_saved_projects_summary(self) -> List[Dict[str, Any]]:
        """
        Get a summary of all projects with saved results.
        
        Returns:
            List of project summaries with saved results info
        """
        summaries = []
        
        try:
            for results_file in self.results_dir.glob("*_results.json"):
                project_id = results_file.stem.replace("_results", "")
                
                try:
                    with open(results_file, 'r') as f:
                        results_package = json.load(f)
                    
                    summary = {
                        "project_id": project_id,
                        "title": results_package.get('project', {}).get('title', 'Unknown'),
                        "saved_at": results_package.get('saved_at'),
                        "completion_status": results_package.get('metadata', {}).get('completion_status'),
                        "total_nodes": results_package.get('metadata', {}).get('total_nodes', 0),
                        "auto_saved": results_package.get('auto_saved', False)
                    }
                    
                    summaries.append(summary)
                
                except Exception as e:
                    logger.warning(f"Failed to read results file {results_file}: {e}")
        
        except Exception as e:
            logger.error(f"Failed to get saved projects summary: {e}")
        
        return sorted(summaries, key=lambda x: x.get('saved_at', ''), reverse=True)
