"""
Broadcasting Utilities

Handles real-time updates and broadcasting to WebSocket clients.
"""

from typing import Dict, Any, Optional, TYPE_CHECKING
import traceback
from loguru import logger
from datetime import datetime

if TYPE_CHECKING:
    from ...core.system_manager import SystemManager

class BroadcastManager:
    """
    Manages broadcasting updates to WebSocket clients.
    
    This class centralizes all broadcasting logic and provides
    consistent error handling and logging.
    """
    
    def __init__(self, socketio, system_manager, project_service):
        """
        Initialize BroadcastManager.
        
        Args:
            socketio: SocketIO instance
            system_manager: SystemManager instance  
            project_service: ProjectService instance
        """
        self.socketio = socketio
        self.system_manager = system_manager
        self.project_service = project_service
    
    def broadcast_graph_update(self) -> bool:
        """
        Send current project's graph state to all connected clients.
        Uses project-specific data instead of shared display graph to prevent conflicts.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.debug("📡 Starting project-specific broadcast...")
            
            # Get current project directly - no shared display graph
            current_project = self.project_service.project_manager.get_current_project()
            
            if current_project:
                # Get project-specific data without affecting other projects
                data = self.project_service.get_project_display_data(current_project.id)
                data['current_project'] = current_project.to_dict()
                
                node_count = len(data.get('all_nodes', {}))
                logger.debug(f"📡 Broadcasting project {current_project.id}: {node_count} nodes")
            else:
                # No current project - send empty state
                data = {
                    'all_nodes': {},
                    'graphs': {},
                    'overall_project_goal': None,
                    'root_graph_id': None,
                    'current_project': None
                }
                logger.debug("📡 Broadcasting empty state (no current project)")
            
            # Emit the project-specific data
            self.socketio.emit('task_graph_update', data)
            
            # Save state for current project (non-blocking)
            if current_project:
                try:
                    self.project_service.save_project_state_async(current_project.id, data)
                except Exception as e:
                    logger.warning(f"Failed to save during broadcast: {e}")
            
            logger.debug("📡 Project-specific broadcast completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Broadcast error: {e}")
            traceback.print_exc()
            return False
    
    def broadcast_project_switch(self, project_id: str) -> bool:
        """
        Broadcast project switch event with immediate data load.
        
        Args:
            project_id: ID of the project being switched to
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"📡 Broadcasting project switch to: {project_id}")
            
            # Get the switched project's data
            project = self.project_service.project_manager.get_project(project_id)
            if not project:
                logger.error(f"Project {project_id} not found for switch broadcast")
                return False
            
            # Load and get project data
            data = self.project_service.get_project_display_data(project_id)
            data['current_project'] = project.to_dict()
            
            # Emit project switch event with data
            self.socketio.emit('project_switched', {
                'project_id': project_id,
                'project_data': data,
                'timestamp': datetime.now().isoformat()
            })
            
            # Also emit regular graph update for compatibility
            self.socketio.emit('task_graph_update', data)
            
            logger.info(f"📡 Project switch broadcast completed for: {project_id}")
            return True
            
        except Exception as e:
            logger.error(f"Project switch broadcast error: {e}")
            traceback.print_exc()
            return False
    
    def broadcast_projects_list(self):
        """Broadcast updated projects list to all clients."""
        try:
            projects_data = self.project_service.get_all_projects()
            self.socketio.emit('projects_list', projects_data)
            logger.debug("📡 Broadcasted projects list update")
        except Exception as e:
            logger.error(f"Failed to broadcast projects list: {e}")
    
    def broadcast_project_status(self, project_id: str, status: str):
        """
        Broadcast project status change.
        
        Args:
            project_id: Project identifier
            status: New project status
        """
        try:
            self.socketio.emit('project_status_update', {
                'project_id': project_id,
                'status': status,
                'timestamp': datetime.now().isoformat()
            })
            logger.debug(f"📡 Broadcasted status update for project {project_id}: {status}")
        except Exception as e:
            logger.error(f"Failed to broadcast project status: {e}")
    
    def broadcast_error(self, error_message: str, context: Optional[Dict[str, Any]] = None):
        """
        Broadcast error message to clients.
        
        Args:
            error_message: Error message to broadcast
            context: Optional context information
        """
        try:
            error_data = {
                'message': error_message,
                'timestamp': datetime.now().isoformat()
            }
            if context:
                error_data['context'] = context
                
            self.socketio.emit('error', error_data)
            logger.debug(f"📡 Broadcasted error: {error_message}")
        except Exception as e:
            logger.error(f"Failed to broadcast error: {e}")
    
    def _serialize_graph_data(self, display_graph) -> Dict[str, Any]:
        """
        Serialize graph data for broadcasting.
        
        Args:
            display_graph: TaskGraph to serialize
            
        Returns:
            Serialized graph data
        """
        try:
            if hasattr(display_graph, 'to_visualization_dict'):
                return display_graph.to_visualization_dict()
            else:
                # Fallback: Import and use GraphSerializer directly
                from ...hierarchical_agent_framework.graph.graph_serializer import GraphSerializer
                serializer = GraphSerializer(display_graph)
                return serializer.to_visualization_dict()
        except Exception as e:
            logger.warning(f"Failed to use to_visualization_dict: {e}")
            # Manual fallback serialization
            return self._manual_serialize_graph(display_graph)
    
    def _manual_serialize_graph(self, display_graph) -> Dict[str, Any]:
        """
        Manual fallback graph serialization.
        
        Args:
            display_graph: TaskGraph to serialize
            
        Returns:
            Manually serialized graph data
        """
        data = {
            'all_nodes': {},
            'graphs': {},
            'overall_project_goal': getattr(display_graph, 'overall_project_goal', None),
            'root_graph_id': getattr(display_graph, 'root_graph_id', None)
        }
        
        # Serialize graphs manually - convert DiGraph objects
        if hasattr(display_graph, 'graphs') and isinstance(display_graph.graphs, dict):
            for graph_id, graph in display_graph.graphs.items():
                try:
                    if hasattr(graph, 'nodes') and hasattr(graph, 'edges'):
                        # It's a NetworkX DiGraph
                        data['graphs'][graph_id] = {
                            'nodes': list(graph.nodes()),
                            'edges': [{"source": u, "target": v} for u, v in graph.edges()]
                        }
                except Exception as e:
                    logger.warning(f"Failed to serialize graph {graph_id}: {e}")
        
        # Serialize nodes manually
        if hasattr(display_graph, 'nodes') and isinstance(display_graph.nodes, dict):
            for node_id, node in display_graph.nodes.items():
                try:
                    # Import the serializer to use its node serialization
                    from ...hierarchical_agent_framework.graph.graph_serializer import GraphSerializer
                    temp_serializer = GraphSerializer(display_graph)
                    data['all_nodes'][node_id] = temp_serializer._serialize_node(node)
                except Exception as e:
                    logger.warning(f"Failed to serialize node {node_id}: {e}")
        
        return data