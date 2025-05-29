"""
HITL (Human-in-the-Loop) WebSocket Handlers

Handles human-in-the-loop interactions via WebSocket.
"""

from flask_socketio import emit
from loguru import logger


def register_hitl_events(socketio):
    """
    Register HITL-specific WebSocket event handlers.
    
    Args:
        socketio: SocketIO instance
    """
    
    @socketio.on('hitl_response')
    def handle_hitl_response_event(data):
        """Handle HITL response from frontend."""
        logger.info(f"📥 Received HITL response: {data}")
        
        try:
            # Import and use the HITL response handler
            from ...hierarchical_agent_framework.utils.websocket_hitl_utils import handle_hitl_response
            handle_hitl_response(data)
        except Exception as e:
            logger.error(f"Failed to handle HITL response: {e}")
            emit('hitl_error', {'message': f'Failed to process HITL response: {str(e)}'})
