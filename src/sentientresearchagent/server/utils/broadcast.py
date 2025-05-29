
"""
Broadcasting Utilities

Handles real-time updates and broadcasting to WebSocket clients.
"""

from typing import Dict, Any, Optional
import traceback
from loguru import logger
from datetime import datetime


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
        Send current graph state to all connected clients with project info.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.debug("📡 Starting broadcast...")
            
            # Get the current display graph
            display_graph = self.system_manager.task_graph
            
            # Check if display graph is corrupted
            if (not hasattr(display_graph, 'nodes') or 
                not hasattr(display_graph, 'graphs') or
                not isinstance(display_graph.nodes, dict) or
                not isinstance(display_graph.graphs, dict)):
                
                logger.warning("Display graph is corrupted, recreating...")
                from ...hierarchical_agent_framework.graph.task_graph import TaskGraph
                self.system_manager.task_graph = TaskGraph()
                display_graph = self.system_manager.task_graph
                
                # Try to restore from current project if available
                current_project = self.project_service.project_manager.get_current_project()
                if current_project and current_project.id in self.project_service.project_graphs:
                    self.project_service.sync_project_to_display(current_project.id)
                    return True  # sync_project_to_display will call broadcast again
            
            # Serialize the graph data
            data = self._serialize_graph_data(display_graph)
            
            # Add current project info
            current_project = self.project_service.project_manager.get_current_project()
            if current_project:
                data['current_project'] = current_project.to_dict()
            
            node_count = len(data.get('all_nodes', {}))
            logger.debug(f"📡 Broadcasting update: {node_count} nodes")
            
            # Emit the data
            self.socketio.emit('task_graph_update', data)
            
            # Save state for current project
            if current_project:
                try:
                    self.project_service.project_manager.save_project_state(current_project.id, data)
                except Exception as e:
                    logger.warning(f"Failed to save during broadcast: {e}")
            
            logger.debug("📡 Broadcast completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Broadcast error: {e}")
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