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
    
    @socketio.on('switch_project')
    def handle_switch_project(data):
        """Handle project switching via WebSocket."""
        logger.info(f"🔄 WebSocket request to switch project: {data}")
        try:
            project_id = data.get('project_id')
            if not project_id:
                emit('project_switch_error', {
                    'error': 'project_id is required'
                })
                return
            
            # Validate project exists
            project = project_service.project_manager.get_project(project_id)
            if not project:
                emit('project_switch_error', {
                    'error': f'Project {project_id} not found'
                })
                return
            
            logger.info(f"🔄 Switching to project: {project_id}")
            
            # Perform the switch
            success = project_service.switch_project(project_id)
            
            if success:
                # Get the switched project's data
                project_data = project_service.get_project_display_data(project_id)
                project_data['current_project'] = project.to_dict()
                
                # Send success response to the requesting client
                emit('project_switch_success', {
                    'project_id': project_id,
                    'project_data': project_data,
                    'message': f'Switched to project: {project.title}'
                })
                
                # Broadcast the project change to all connected clients
                socketio.emit('project_switched', {
                    'project_id': project_id,
                    'project_data': project_data,
                    'timestamp': datetime.now().isoformat()
                })
                
                # Also send regular graph update for compatibility
                socketio.emit('task_graph_update', project_data)
                
                logger.info(f"✅ Project switched to {project_id} via WebSocket")
            else:
                emit('project_switch_error', {
                    'error': f'Failed to switch to project {project_id}'
                })
                logger.error(f"❌ Failed to switch project via WebSocket: {project_id}")
                
        except Exception as e:
            logger.error(f"WebSocket project switch error: {e}")
            emit('project_switch_error', {
                'error': str(e)
            })
    
    @socketio.on('restore_project_state')
    def handle_restore_project_state(data):
        """Handle project state restoration request."""
        logger.info(f"🔄 WebSocket request to restore project state: {data}")
        try:
            project_id = data.get('project_id')
            if not project_id:
                emit('project_restore_error', {
                    'error': 'project_id is required'
                })
                return
            
            # Get project data
            project = project_service.project_manager.get_project(project_id)
            if not project:
                emit('project_restore_error', {
                    'error': f'Project {project_id} not found'
                })
                return
            
            # Get project display data
            project_data = project_service.get_project_display_data(project_id)
            project_data['current_project'] = project.to_dict()
            
            # Send restored data
            emit('project_restored', project_data)
            
            logger.info(f"✅ Project state restored for {project_id}")
            
        except Exception as e:
            logger.error(f"WebSocket project restore error: {e}")
            emit('project_restore_error', {
                'error': str(e)
            })
    
    @socketio.on('auto_save_project')
    def handle_auto_save_project(data):
        """Handle automatic project saving from frontend."""
        try:
            project_id = data.get('project_id')
            project_data = data.get('data')
            
            if not project_id or not project_data:
                logger.warning("Auto-save request missing project_id or data")
                return
            
            logger.info(f"💾 Auto-saving project data: {project_id}")
            
            # Save to project service
            project_service.save_project_state_async(project_id, project_data)
            
            # Also save as results for persistence
            results_package = {
                "project_id": project_id,
                "saved_at": datetime.now().isoformat(),
                "graph_data": project_data,
                "auto_saved": True,
                "metadata": {
                    "total_nodes": len(project_data.get('all_nodes', {})),
                    "project_goal": project_data.get('overall_project_goal'),
                    "completion_status": "auto_saved"
                }
            }
            
            project_service.save_project_results(project_id, results_package)
            
            logger.info(f"✅ Auto-saved project: {project_id}")
            
        except Exception as e:
            logger.error(f"Auto-save error: {e}")
    
    @socketio.on('request_project_restore')
    def handle_request_project_restore(data):
        """Handle project state restoration requests with enhanced debugging."""
        try:
            project_id = data.get('project_id')
            if not project_id:
                emit('project_restore_error', {'error': 'project_id required'})
                return

            logger.info(f"🔄 Restoring project state: {project_id}")

            # ENHANCED: Try multiple restoration sources
            restored = False
            
            # 1. Try to load comprehensive saved results first
            results = project_service.load_project_results(project_id)
            if results and results.get('basic_state'):
                project_data = results['basic_state']
                project_data['project_id'] = project_id
                project_data['restored'] = True
                project_data['restored_at'] = datetime.now().isoformat()
                project_data['restored_from'] = 'comprehensive_results'
                
                # AGGRESSIVE DEBUGGING
                node_count = len(project_data.get('all_nodes', {}))
                logger.info(f"🚨 RESTORE DEBUG - From comprehensive results: {node_count} nodes")
                
                if project_data.get('all_nodes'):
                    for node_id, node_data in list(project_data['all_nodes'].items())[:3]:
                        has_full_result = bool(node_data.get('full_result'))
                        logger.info(f"🚨 RESTORE DEBUG - Node {node_id}: has_full_result={has_full_result}")

                emit('project_restored', project_data)
                logger.info(f"✅ Restored project from comprehensive results: {project_id}")
                restored = True

            # 2. Fallback to basic project state
            if not restored:
                project_state = project_service.project_manager.load_project_state(project_id)
                if project_state:
                    project_state['project_id'] = project_id
                    project_state['restored'] = True
                    project_state['restored_at'] = datetime.now().isoformat()
                    project_state['restored_from'] = 'basic_state'

                    # AGGRESSIVE DEBUGGING
                    node_count = len(project_state.get('all_nodes', {}))
                    logger.info(f"🚨 RESTORE DEBUG - From basic state: {node_count} nodes")

                    emit('project_restored', project_state)
                    logger.info(f"✅ Restored project from basic state: {project_id}")
                    restored = True

            if not restored:
                emit('project_restore_error', {'error': f'No saved state found for project {project_id}'})
                logger.warning(f"❌ No saved state found for project: {project_id}")

        except Exception as e:
            logger.error(f"Project restore error: {e}")
            import traceback
            traceback.print_exc()
            emit('project_restore_error', {'error': str(e)})

    # NEW: Manual save trigger
    @socketio.on('force_save_project')
    def handle_force_save_project(data):
        """Force save current project state - useful for debugging."""
        try:
            project_id = data.get('project_id')
            if not project_id:
                emit('save_error', {'error': 'project_id required'})
                return

            logger.info(f"🚨 FORCE SAVE - Manually saving project: {project_id}")
            
            # Get current project data
            project_data = project_service.get_project_display_data(project_id)
            
            # Save comprehensive results
            results_package = {
                'basic_state': project_data,
                'saved_at': datetime.now().isoformat(),
                'manual_save': True,
                'metadata': {
                    'node_count': len(project_data.get('all_nodes', {})),
                    'project_goal': project_data.get('overall_project_goal'),
                    'completion_status': 'manual_save'
                }
            }
            
            success = project_service.save_project_results(project_id, results_package)
            
            if success:
                emit('save_success', {
                    'project_id': project_id,
                    'message': 'Project saved successfully',
                    'node_count': len(project_data.get('all_nodes', {}))
                })
                logger.info(f"✅ FORCE SAVE - Successfully saved project: {project_id}")
            else:
                emit('save_error', {'error': 'Failed to save project'})
                logger.error(f"❌ FORCE SAVE - Failed to save project: {project_id}")

        except Exception as e:
            logger.error(f"Force save error: {e}")
            emit('save_error', {'error': str(e)})
    
    @socketio.on('start_project_execution')
    def handle_start_project_execution(data):
        """Handle project re-execution requests."""
        try:
            project_id = data.get('project_id')
            goal = data.get('goal')
            max_steps = data.get('max_steps', 250)
            
            if not project_id or not goal:
                emit('execution_error', {'error': 'project_id and goal are required'})
                return
            
            logger.info(f"🚨 RE-EXECUTION - Starting execution for project: {project_id}")
            logger.info(f"🚨 RE-EXECUTION - Goal: {goal}")
            
            # Clear any existing state for this project
            project_service.project_manager.update_project(project_id, status='running', node_count=0)
            
            # Start execution
            success = execution_service.start_project_execution(project_id, goal, max_steps)
            
            if success:
                emit('execution_started', {
                    'project_id': project_id,
                    'message': f'Re-execution started for project {project_id}',
                    'goal': goal,
                    'max_steps': max_steps
                })
                logger.info(f"✅ RE-EXECUTION - Started successfully for project: {project_id}")
            else:
                emit('execution_error', {
                    'error': f'Failed to start execution for project {project_id}'
                })
                logger.error(f"❌ RE-EXECUTION - Failed to start for project: {project_id}")
            
        except Exception as e:
            logger.error(f"Re-execution error: {e}")
            emit('execution_error', {'error': str(e)})
    
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
