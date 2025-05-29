"""
Flask Application Factory

Creates and configures the Flask app and SocketIO instance.
"""

from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
from typing import Optional
import os


def create_app(config: Optional[dict] = None) -> Flask:
    """
    Create and configure Flask application.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        Configured Flask application
    """
    app = Flask(__name__)
    
    # Default configuration
    app.config.update({
        'SECRET_KEY': os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here'),
        'DEBUG': os.getenv('FLASK_DEBUG', 'false').lower() == 'true',
    })
    
    # Apply custom config if provided
    if config:
        app.config.update(config)
    
    # Setup CORS
    CORS(app, origins=[
        "http://localhost:3000", 
        "http://127.0.0.1:3000"
    ])
    
    return app


def create_socketio(app: Flask) -> SocketIO:
    """
    Create and configure SocketIO instance.
    
    Args:
        app: Flask application instance
        
    Returns:
        Configured SocketIO instance
    """
    socketio = SocketIO(
        app,
        cors_allowed_origins="*",
        async_mode='threading',
        logger=True,
        engineio_logger=True
    )
    
    return socketio


def register_routes(app: Flask, socketio: SocketIO, system_manager, project_service, execution_service):
    """
    Register all routes and event handlers.
    
    Args:
        app: Flask application
        socketio: SocketIO instance  
        system_manager: System manager instance
        project_service: Project service instance
        execution_service: Execution service instance
    """
    # Register REST API routes
    from .api.system import create_system_routes
    from .api.projects import create_project_routes
    from .api.simple_api import create_simple_api_routes
    
    create_system_routes(app, system_manager)
    create_project_routes(app, project_service, execution_service)
    create_simple_api_routes(app, system_manager)
    
    # Register WebSocket event handlers
    from .websocket.events import register_websocket_events
    from .websocket.hitl import register_hitl_events
    
    register_websocket_events(socketio, project_service, execution_service)
    register_hitl_events(socketio)
