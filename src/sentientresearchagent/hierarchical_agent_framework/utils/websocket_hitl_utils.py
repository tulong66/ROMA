"""
WebSocket-based Human-in-the-Loop utilities
"""
import asyncio
import uuid
import os
from datetime import datetime
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Global reference to the socketio instance
_socketio_instance = None

# Global storage for pending HITL requests
_pending_requests = {}

# Global timeout setting (will be set by the system)
_hitl_timeout_seconds = 1800.0  # Default 30 minutes, but will be overridden

def set_socketio_instance(socketio):
    """Set the global socketio instance for HITL communication"""
    global _socketio_instance
    _socketio_instance = socketio
    logger.info("WebSocket HITL: socketio instance registered")

def set_hitl_timeout(timeout_seconds: float):
    """Set the HITL timeout from configuration"""
    global _hitl_timeout_seconds
    _hitl_timeout_seconds = timeout_seconds
    logger.info(f"WebSocket HITL: timeout set to {timeout_seconds} seconds")

def check_connected_clients():
    """Check if there are any connected clients"""
    global _socketio_instance
    if not _socketio_instance:
        return 0
    
    try:
        if hasattr(_socketio_instance.server, 'manager') and hasattr(_socketio_instance.server.manager, 'rooms'):
            rooms = _socketio_instance.server.manager.rooms
            if '/' in rooms:
                return len(rooms['/'])
        return 0
    except Exception as e:
        logger.error(f"Error checking connected clients: {e}")
        return 0

async def websocket_human_review(
    checkpoint_name: str,
    context_message: str,
    data_for_review: Optional[Any] = None,
    node_id: Optional[str] = "N/A",
    current_attempt: int = 1
) -> Dict[str, Any]:
    """
    WebSocket-based human review that broadcasts HITL requests to frontend
    """
    global _socketio_instance, _pending_requests, _hitl_timeout_seconds
    
    logger.info(f"🤔 HITL WebSocket: Broadcasting checkpoint '{checkpoint_name}' for node {node_id}")
    
    if not _socketio_instance:
        logger.error("🚨 HITL WebSocket: No socketio instance available!")
        return {
            "user_choice": "approved",
            "message": f"Auto-approved checkpoint '{checkpoint_name}' (no socketio instance)",
            "modification_instructions": None
        }
    
    # Check if there are connected clients
    connected_clients = check_connected_clients()
    logger.info(f"🔍 Connected clients: {connected_clients}")
    
    if connected_clients == 0:
        logger.warning("⚠️ No connected clients, but proceeding with HITL request")
        # Don't auto-approve, still send the request in case client reconnects
    
    # Create HITL request
    request_id = str(uuid.uuid4())
    hitl_request = {
        "checkpoint_name": checkpoint_name,
        "context_message": context_message,
        "data_for_review": data_for_review,
        "node_id": node_id,
        "current_attempt": current_attempt,
        "request_id": request_id,
        "timestamp": datetime.now().isoformat()
    }
    
    # Store the request for response handling
    response_future = asyncio.Future()
    _pending_requests[request_id] = response_future
    
    try:
        logger.info("📡 Emitting HITL request to frontend")
        _socketio_instance.emit('hitl_request', hitl_request)
        logger.info("✅ HITL request emitted successfully")
        
        # Wait for response with configured timeout
        # Use a much longer timeout to prevent auto-approval
        actual_timeout = max(_hitl_timeout_seconds, 3600)  # At least 1 hour
        
        try:
            logger.info(f"⏳ Waiting for user response to HITL request {request_id} (timeout: {actual_timeout}s)...")
            
            # Periodically re-emit the request in case of connection drops
            async def periodic_reemit():
                emit_count = 0
                while not response_future.done():
                    await asyncio.sleep(30)  # Re-emit every 30 seconds
                    if not response_future.done():
                        emit_count += 1
                        current_clients = check_connected_clients()
                        logger.info(f"🔄 Re-emitting HITL request {request_id} (attempt {emit_count}, clients: {current_clients})")
                        try:
                            _socketio_instance.emit('hitl_request', hitl_request)
                        except Exception as e:
                            logger.error(f"Error re-emitting HITL request: {e}")
            
            # Start the periodic re-emit task
            reemit_task = asyncio.create_task(periodic_reemit())
            
            try:
                response = await asyncio.wait_for(response_future, timeout=actual_timeout)
                logger.info(f"✅ Received HITL response: {response}")
                return response
            finally:
                # Cancel the re-emit task
                reemit_task.cancel()
                try:
                    await reemit_task
                except asyncio.CancelledError:
                    pass
                    
        except asyncio.TimeoutError:
            logger.warning(f"⏰ HITL request {request_id} timed out after {actual_timeout} seconds")
            # Still don't auto-approve, return timeout status
            return {
                "user_choice": "timeout",
                "message": f"HITL request timed out after {actual_timeout} seconds",
                "modification_instructions": None
            }
        
    except Exception as e:
        logger.error(f"❌ Error during HITL request: {e}")
        return {
            "user_choice": "error",
            "message": f"Error during HITL request: {e}",
            "modification_instructions": None
        }
    finally:
        # Clean up
        _pending_requests.pop(request_id, None)

def handle_hitl_response(response_data: Dict[str, Any]):
    """Handle HITL response from frontend"""
    global _pending_requests
    
    request_id = response_data.get('request_id')
    if not request_id:
        logger.error("❌ HITL response missing request_id")
        return
    
    future = _pending_requests.get(request_id)
    if not future:
        logger.warning(f"⚠️ No pending request found for ID: {request_id}")
        return
    
    action = response_data.get('action')
    modification_instructions = response_data.get('modification_instructions')
    
    # Convert frontend action to backend format
    if action == 'approve':
        user_choice = 'approved'
        message = f"User approved checkpoint '{response_data.get('checkpoint_name')}'"
    elif action == 'modify':
        user_choice = 'request_modification'
        message = f"User requested modification for '{response_data.get('checkpoint_name')}'"
    elif action == 'abort':
        user_choice = 'aborted'
        message = f"User aborted checkpoint '{response_data.get('checkpoint_name')}'"
    else:
        user_choice = 'approved'
        message = f"Unknown action '{action}', defaulting to approved"
    
    result = {
        "user_choice": user_choice,
        "message": message,
        "modification_instructions": modification_instructions
    }
    
    # Resolve the future with the response
    if not future.done():
        future.set_result(result)
        logger.info(f"✅ HITL response processed for request {request_id}: {user_choice}")