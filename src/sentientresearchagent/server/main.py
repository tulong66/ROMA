"""
Main Server Module

Contains the main server class and factory functions.
"""

from loguru import logger
import os

from .app import create_app, create_socketio, register_routes
from .services import SystemManager, ProjectService, ExecutionService
from .utils import BroadcastManager


class SentientServer:
    """
    Main server class that orchestrates all components.
    
    This class follows the application factory pattern and provides
    a clean, testable interface for the server.
    """
    
    def __init__(self, config: dict = None):
        """
        Initialize the server.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.app = None
        self.socketio = None
        self.system_manager = None
        self.project_service = None
        self.execution_service = None
        self.broadcast_manager = None
        
    def create(self):
        """
        Create and configure all server components.
        
        Returns:
            Tuple of (app, socketio) for running the server
        """
        logger.info("🚀 Creating Sentient Research Agent Server...")
        
        # Create Flask app and SocketIO
        self.app = create_app(self.config)
        self.socketio = create_socketio(self.app)
        
        # Initialize core services
        logger.info("🔧 Initializing core services...")
        self.system_manager = SystemManager()
        self.system_manager.initialize()
        
        # Setup WebSocket HITL integration
        self.system_manager.setup_websocket_hitl(self.socketio)
        
        # Create broadcast manager
        self.broadcast_manager = BroadcastManager(
            self.socketio, 
            self.system_manager, 
            None  # Will be set after project service is created
        )
        
        # Create project service with broadcast callback
        self.project_service = ProjectService(
            self.system_manager,
            self.broadcast_manager.broadcast_graph_update
        )
        
        # Update broadcast manager with project service
        self.broadcast_manager.project_service = self.project_service
        
        # Create execution service
        self.execution_service = ExecutionService(
            self.project_service,
            self.system_manager
        )
        
        # Register all routes and event handlers
        logger.info("📡 Registering routes and event handlers...")
        register_routes(
            self.app, 
            self.socketio, 
            self.system_manager, 
            self.project_service, 
            self.execution_service
        )
        
        logger.info("✅ Server created successfully!")
        return self.app, self.socketio
    
    def run(self, host='0.0.0.0', port=5000, debug=False):
        """
        Run the server.
        
        Args:
            host: Host to bind to
            port: Port to bind to
            debug: Enable debug mode
        """
        if not self.app or not self.socketio:
            self.create()
        
        logger.info(f"🚀 Starting Sentient Research Agent Server on {host}:{port}")
        logger.info("📡 WebSocket: http://localhost:5000")
        logger.info("🌐 Frontend: http://localhost:3000")
        logger.info("📊 System Info: http://localhost:5000/api/system-info")
        logger.info("")
        logger.info("🎯 Simple API Endpoints:")
        logger.info("   POST /api/simple/execute - Execute any goal")
        logger.info("   POST /api/simple/research - Quick research tasks")
        logger.info("   POST /api/simple/analysis - Quick analysis tasks")
        logger.info("   GET  /api/simple/status - Simple API status")
        logger.info("   WebSocket: simple_execute_stream - Streaming execution")
        logger.info("")
        logger.info("📚 Example usage:")
        logger.info("   curl -X POST http://localhost:5000/api/simple/research \\")
        logger.info("        -H 'Content-Type: application/json' \\")
        logger.info("        -d '{\"topic\": \"quantum computing applications\"}'")
        
        try:
            self.socketio.run(
                self.app, 
                debug=debug, 
                host=host, 
                port=port, 
                use_reloader=False
            )
        except Exception as e:
            logger.error(f"❌ Server startup error: {e}")
            import traceback
            traceback.print_exc()


def create_server(config: dict = None) -> SentientServer:
    """
    Factory function to create a server instance.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        SentientServer instance
    """
    return SentientServer(config)


# For backward compatibility with the original server
def main():
    """Main entry point for the server."""
    server = create_server()
    server.run()


if __name__ == '__main__':
    main() 