"""
Main Server Module V2 - Using refactored components

This version uses the new SystemManagerV2 with refactored components.
"""

from loguru import logger
import os
from typing import Optional

from ..server.app import create_app, create_socketio, register_routes
from ..server.services import ProjectService, ExecutionService
from ..core.system_manager_v2 import SystemManagerV2  # Use V2!
from ..server.utils import BroadcastManager
from ..config import SentientConfig, auto_load_config


class SentientServerV2:
    """
    Main server class using refactored components.
    """
    
    def __init__(self, config_input: Optional[SentientConfig] = None):
        """Initialize the server with refactored components."""
        # Ensure self.config is ALWAYS a SentientConfig instance
        if config_input is None:
            logger.info("SentientServerV2: No config provided, auto-loading...")
            self.config: SentientConfig = auto_load_config()
        elif isinstance(config_input, SentientConfig):
            self.config: SentientConfig = config_input
            logger.info("SentientServerV2: Initialized with provided SentientConfig instance.")
        else:
            logger.warning(f"SentientServerV2: Received config_input of type {type(config_input)}, not SentientConfig.")
            self.config: SentientConfig = auto_load_config()
        
        self.app = None
        self.socketio = None
        self.system_manager = None
        self.project_service = None
        self.execution_service = None
        self.broadcast_manager = None
        
    def create(self):
        """Create and configure all server components with refactored architecture."""
        logger.info("🚀 Creating Sentient Research Agent Server V2 (Refactored)...")
        
        # Create Flask app and SocketIO
        self.app = create_app(self.config)
        self.socketio = create_socketio(self.app)
        
        # Initialize core services with V2
        logger.info("🔧 Initializing core services with refactored components...")
        self.system_manager = SystemManagerV2(config=self.config)
        
        # Get default profile
        default_profile_to_use = self.config.default_profile 
        logger.info(f"🎯 Using default profile from config: {default_profile_to_use}")
        
        try:
            self.system_manager.initialize_with_profile(default_profile_to_use)
        except Exception as e:
            logger.error(f"Failed to initialize SystemManagerV2 with profile '{default_profile_to_use}': {e}")
            raise
        
        # Setup WebSocket HITL integration
        logger.info("🔌 Setting up WebSocket HITL integration...")
        self.system_manager.setup_websocket_hitl(self.socketio)
        
        # Verify WebSocket HITL is ready
        if self.system_manager.config and self.system_manager.config.execution.enable_hitl:
            if self.system_manager.is_websocket_hitl_ready():
                logger.info("✅ WebSocket HITL verified as ready")
            else:
                logger.error("❌ WebSocket HITL setup failed or not available!")
        
        # Create broadcast manager
        self.broadcast_manager = BroadcastManager(
            self.socketio, 
            self.system_manager, 
            None  # Will be set after project_service is created
        )
        
        # Create project service with broadcast callback
        self.project_service = ProjectService(
            self.system_manager,
            self.broadcast_manager.broadcast_graph_update
        )
        
        # Update broadcast manager with project service
        self.broadcast_manager.project_service = self.project_service
        self.project_service.broadcast_manager = self.broadcast_manager
        
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
        
        # Final readiness check
        if self.system_manager.config and self.system_manager.config.execution.enable_hitl:
            hitl_status = self.system_manager.get_websocket_hitl_status()
            logger.info(f"🎮 Final HITL Status: {hitl_status}")
        
        # Log system info
        system_info = self.system_manager.get_system_info()
        logger.info(f"📊 System Info: {system_info}")
        
        logger.success("✅ Server V2 created successfully with refactored components!")
        return self.app, self.socketio
    
    def run(self, host='0.0.0.0', port=5000, debug=False):
        """Run the server."""
        if not self.app or not self.socketio:
            self.create()
        
        logger.info(f"🚀 Starting Sentient Research Agent Server V2 on {host}:{port}")
        logger.info("✨ Using refactored modular architecture")
        logger.info("📡 WebSocket: http://localhost:5000")
        logger.info("🌐 Frontend: http://localhost:3000")
        logger.info("📊 System Info: http://localhost:5000/api/system-info")
        
        try:
            self.socketio.run(
                self.app, 
                debug=debug, 
                host=host, 
                port=port, 
                use_reloader=False,
                allow_unsafe_werkzeug=True
            )
        except Exception as e:
            logger.error(f"❌ Server startup error: {e}")
            import traceback
            traceback.print_exc()


def create_server_v2(config: Optional[SentientConfig] = None) -> SentientServerV2:
    """Factory function to create a server V2 instance."""
    return SentientServerV2(config)


def main():
    """Main entry point for server V2."""
    import argparse
    parser = argparse.ArgumentParser(description='Sentient Research Agent Server V2')
    parser.add_argument('--port', type=int, default=5000, help='Port to run server on')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()
    
    server = create_server_v2() 
    server.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()