"""
WebSocket Event Handlers

Main WebSocket event handlers for the application.
"""

import threading
from flask_socketio import emit
from loguru import logger
from datetime import datetime

from ..utils.validation import RequestValidator


def register_websocket_events(socketio, project_service, execution_service):
    """
    Register WebSocket event handlers.
    
    Args:
        socketio: SocketIO instance
        project_service: ProjectService instance
        execution_service: ExecutionService instance
    """
    
    @socketio.on('connect')
    def handle_connect(auth):
        """Handle client connection."""
        logger.info('👋 Client connected')
        try:
            # Send initial state
            handle_request_initial_state()
        except Exception as e:
            logger.error(f"Error in connect handler: {e}")
    
    @socketio.on('disconnect')
    def handle_disconnect(auth=None):
        """Handle client disconnection."""
        try:
            logger.info('👋 Client disconnected')
            # Don't emit anything on disconnect - client is already gone
            # Just log and clean up any resources if needed
        except Exception as e:
            logger.error(f"Error in disconnect handler: {e}")
    
    @socketio.on('request_initial_state')
    def handle_request_initial_state():
        """Send initial state when frontend connects."""
        logger.info('📋 Client requested initial state')
        try:
            # Send project list
            projects_data = project_service.get_all_projects()
            emit('projects_list', projects_data)
            
            # If there's a current project, send its graph
            current_project = project_service.project_manager.get_current_project()
            if current_project:
                project_service.load_project_into_graph(current_project.id)
            else:
                # Send empty graph by triggering broadcast
                if hasattr(project_service, 'broadcast_callback') and project_service.broadcast_callback:
                    project_service.broadcast_callback()
                
        except Exception as e:
            logger.error(f"Error sending initial state: {e}")
            # Only emit error if we're still connected
            try:
                emit('error', {'message': 'Failed to load initial state'})
            except:
                pass  # Client might have disconnected
    
    @socketio.on('start_project')
    def handle_start_project(data):
        """Handle project start request."""
        logger.info(f"🚀 Received start_project: {data}")
        try:
            # Validate required fields
            if not data or 'project_goal' not in data:
                emit('error', {'message': 'project_goal not provided'})
                return
            
            project_goal = data['project_goal']
            max_steps = data.get('max_steps', 250)  # Should get from config
            project_id = data.get('project_id')  # Optional project ID
            
            # Validate goal
            goal_valid, goal_error = RequestValidator.validate_project_goal(project_goal)
            if not goal_valid:
                emit('error', {'message': goal_error})
                return
            
            # Validate max_steps
            steps_valid, steps_error, validated_steps = RequestValidator.validate_max_steps(max_steps)
            if not steps_valid:
                emit('error', {'message': steps_error})
                return
            
            # Create or use existing project
            if project_id:
                project_data = project_service.get_project(project_id)
                if not project_data:
                    emit('error', {'message': 'Project not found'})
                    return
                project_dict = project_data['project']
            else:
                project_dict = project_service.create_project(project_goal, validated_steps)
                project_id = project_dict['id']
            
            logger.info(f"🚀 Starting project: {project_id} - {project_goal}")
            
            # Start in background thread
            success = execution_service.start_project_execution(project_id, project_goal, validated_steps)
            
            if not success:
                emit('error', {'message': 'Failed to start project execution'})
                return
            
            emit('project_started', {
                'message': f"Project started: {project_goal}",
                'project': project_dict
            })
            logger.info("✅ Project started response sent")
            
        except Exception as e:
            logger.error(f"Error in start_project handler: {e}")
            emit('error', {'message': f'Server error: {str(e)}'})
    
    @socketio.on('simple_execute_stream')
    def handle_simple_execute_stream(data):
        """WebSocket handler for streaming simple API execution."""
        logger.info(f"🌊 Received simple_execute_stream: {data}")
        try:
            # Check framework availability
            try:
                from ...framework_entry import FRAMEWORK_AVAILABLE
            except ImportError:
                FRAMEWORK_AVAILABLE = False
                
            if not FRAMEWORK_AVAILABLE:
                emit('simple_execution_error', {'message': 'Framework components not available'})
                return
                
            goal = data.get('goal')
            if not goal:
                emit('simple_execution_error', {'message': 'goal not provided'})
                return
            
            # Validate goal
            goal_valid, goal_error = RequestValidator.validate_project_goal(goal)
            if not goal_valid:
                emit('simple_execution_error', {'message': goal_error})
                return
            
            options = data.get('options', {})
            
            # Start streaming execution in background thread
            thread = threading.Thread(
                target=_run_simple_streaming_execution, 
                args=(socketio, goal, options),
                daemon=True
            )
            thread.start()
            
            emit('simple_execution_started', {
                'message': f"Simple execution started: {goal[:50]}...",
                'goal': goal
            })
            
        except Exception as e:
            logger.error(f"Simple execute stream error: {e}")
            emit('simple_execution_error', {'message': f'Error: {str(e)}'})
    
    @socketio.on_error_default
    def default_error_handler(e):
        """Default error handler for WebSocket events."""
        logger.error(f"SocketIO error: {e}")
        # Don't emit anything here - might cause more connection issues


def _run_simple_streaming_execution(socketio, goal: str, options: dict):
    """
    Run simple API execution with streaming updates.
    
    Args:
        socketio: SocketIO instance for emitting updates
        goal: Execution goal
        options: Execution options
    """
    try:
        # This would need access to the system manager to get the simple agent
        # For now, we'll import it directly
        from ...framework_entry import SimpleSentientAgent
        
        agent = SimpleSentientAgent.create(enable_hitl=False)
        if not agent:
            socketio.emit('simple_execution_error', {'message': 'Failed to get SimpleSentientAgent'})
            return
        
        logger.info(f"🌊 Starting streaming execution: {goal}")
        
        # Use the streaming method from SimpleSentientAgent
        for update in agent.stream_execution(goal, **options):
            socketio.emit('simple_execution_update', update)
            import time
            time.sleep(0.1)  # Small delay to prevent overwhelming the client
        
        logger.info(f"✅ Streaming execution completed: {goal}")
        
    except Exception as e:
        logger.error(f"Streaming execution failed: {e}")
        socketio.emit('simple_execution_error', {
            'message': f'Streaming execution failed: {str(e)}',
            'goal': goal
        })
