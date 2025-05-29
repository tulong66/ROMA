"""
System API Routes

REST endpoints for system information and management.
"""

from flask import jsonify, make_response
from loguru import logger


def create_system_routes(app, system_manager):
    """
    Create system-related API routes.
    
    Args:
        app: Flask application instance
        system_manager: SystemManager instance
    """
    
    @app.route('/api/system-info', methods=['GET'])
    def get_system_info():
        """Get system information and statistics."""
        try:
            info = system_manager.get_system_info()
            return jsonify(info)
        except Exception as e:
            logger.error(f"System info error: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/task-graph', methods=['GET'])
    def get_task_graph_data():
        """Get current graph data."""
        try:
            display_graph = system_manager.task_graph
            if hasattr(display_graph, 'to_visualization_dict'):
                data = display_graph.to_visualization_dict()
            else:
                # Fallback: Import and use GraphSerializer directly
                from ...hierarchical_agent_framework.graph.graph_serializer import GraphSerializer
                serializer = GraphSerializer(display_graph)
                data = serializer.to_visualization_dict()
                
            response = make_response(jsonify(data))
            response.headers['Access-Control-Allow-Origin'] = 'http://localhost:3000'
            return response
        except Exception as e:
            logger.error(f"Task graph endpoint error: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/health', methods=['GET'])
    def health_check():
        """Health check endpoint."""
        try:
            return jsonify({
                "status": "healthy",
                "initialized": system_manager._initialized,
                "timestamp": "2024-01-01T00:00:00Z"  # You'd use datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return jsonify({"error": str(e)}), 500
