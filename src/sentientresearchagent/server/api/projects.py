"""
Project API Routes

REST endpoints for project management.
"""

from flask import jsonify, request
from loguru import logger
from datetime import datetime

from ..utils.validation import RequestValidator


def create_project_routes(app, project_service, execution_service):
    """
    Create project-related API routes.
    
    Args:
        app: Flask application instance
        project_service: ProjectService instance
        execution_service: ExecutionService instance
    """
    
    @app.route('/api/projects', methods=['GET'])
    def get_projects():
        """Get all projects."""
        try:
            projects_data = project_service.get_all_projects()
            return jsonify(projects_data)
        except Exception as e:
            logger.error(f"Get projects error: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/projects', methods=['POST'])
    def create_project():
        """Create a new project."""
        try:
            # Validate request
            is_valid, error_msg, data = RequestValidator.validate_json_required(['goal'])
            if not is_valid:
                return jsonify({"error": error_msg}), 400
            
            goal = data['goal']
            max_steps = data.get('max_steps', 250)  # Default from config would be better
            
            # Validate goal
            goal_valid, goal_error = RequestValidator.validate_project_goal(goal)
            if not goal_valid:
                return jsonify({"error": goal_error}), 400
            
            # Validate max_steps
            steps_valid, steps_error, validated_steps = RequestValidator.validate_max_steps(max_steps)
            if not steps_valid:
                return jsonify({"error": steps_error}), 400
            
            # Create project
            project_dict = project_service.create_project(goal, validated_steps)
            
            # Start project execution in background
            success = execution_service.start_project_execution(
                project_dict['id'], goal, validated_steps
            )
            
            if not success:
                return jsonify({"error": "Failed to start project execution"}), 500
            
            return jsonify({
                "project": project_dict,
                "message": "Project created and started"
            }), 201
            
        except Exception as e:
            logger.error(f"Create project error: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/projects/configured', methods=['POST'])
    def create_configured_project():
        """Create a new project with custom configuration."""
        try:
            # Validate request
            is_valid, error_msg, data = RequestValidator.validate_json_required(['goal', 'config'])
            if not is_valid:
                return jsonify({"error": error_msg}), 400
            
            goal = data['goal']
            config_data = data['config']
            max_steps = data.get('max_steps', 250)
            
            # Validate goal
            goal_valid, goal_error = RequestValidator.validate_project_goal(goal)
            if not goal_valid:
                return jsonify({"error": goal_error}), 400
            
            # Validate config
            config_valid, config_error = RequestValidator.validate_project_config(config_data)
            if not config_valid:
                return jsonify({"error": config_error}), 400
            
            # Validate max_steps
            steps_valid, steps_error, validated_steps = RequestValidator.validate_max_steps(max_steps)
            if not steps_valid:
                return jsonify({"error": steps_error}), 400
            
            # Create a custom config for this project
            custom_config = _create_project_config(config_data)
            
            # Create project
            project_dict = project_service.create_project(goal, validated_steps, custom_config)
            
            # Start project execution with custom config in background
            success = execution_service.start_configured_project_execution(
                project_dict['id'], goal, validated_steps, custom_config
            )
            
            if not success:
                return jsonify({"error": "Failed to start configured project execution"}), 500
            
            return jsonify({
                "project": project_dict,
                "message": "Configured project created and started",
                "config_applied": True
            }), 201
            
        except Exception as e:
            logger.error(f"Create configured project error: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/projects/<project_id>', methods=['GET'])
    def get_project(project_id: str):
        """Get a specific project and its state."""
        try:
            project_data = project_service.get_project(project_id)
            if not project_data:
                return jsonify({"error": "Project not found"}), 404
            
            return jsonify(project_data)
            
        except Exception as e:
            logger.error(f"Get project error: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/projects/<project_id>/switch', methods=['POST'])
    def switch_project(project_id: str):
        """Switch to a different project."""
        try:
            success = project_service.switch_project(project_id)
            if not success:
                return jsonify({"error": "Failed to switch project"}), 500
            
            project_data = project_service.get_project(project_id)
            return jsonify({
                "project": project_data['project'] if project_data else None,
                "message": f"Switched to project {project_id}"
            })
            
        except Exception as e:
            logger.error(f"Switch project error: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/projects/<project_id>', methods=['DELETE'])
    def delete_project(project_id: str):
        """Delete a project."""
        try:
            success = project_service.delete_project(project_id)
            if not success:
                return jsonify({"error": "Project not found"}), 404
            
            return jsonify({"message": "Project deleted successfully"})
            
        except Exception as e:
            logger.error(f"Delete project error: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/projects/<project_id>/config', methods=['GET'])
    def get_project_config(project_id: str):
        """Get the configuration used for a specific project."""
        try:
            config_data = project_service.get_project_config(project_id)
            if not config_data:
                return jsonify({"error": "Project configuration not found"}), 404
            
            return jsonify({
                "project_id": project_id,
                "config": config_data
            })
            
        except Exception as e:
            logger.error(f"Get project config error: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/executions', methods=['GET'])
    def get_running_executions():
        """Get information about currently running executions."""
        try:
            executions = execution_service.get_running_executions()
            return jsonify({"running_executions": executions})
        except Exception as e:
            logger.error(f"Get executions error: {e}")
            return jsonify({"error": str(e)}), 500


def _create_project_config(config_data):
    """Create a SentientConfig from frontend configuration data."""
    from ...config import SentientConfig, LLMConfig, ExecutionConfig, CacheConfig
    
    try:
        # Create config components
        llm_config = LLMConfig(
            provider=config_data['llm']['provider'],
            model=config_data['llm']['model'],
            temperature=config_data['llm']['temperature'],
            max_tokens=config_data['llm'].get('max_tokens'),
            timeout=config_data['llm']['timeout'],
            max_retries=config_data['llm']['max_retries']
        )
        
        execution_config = ExecutionConfig(
            max_concurrent_nodes=config_data['execution']['max_concurrent_nodes'],
            max_execution_steps=config_data['execution']['max_execution_steps'],
            enable_hitl=config_data['execution']['enable_hitl'],
            hitl_root_plan_only=config_data['execution']['hitl_root_plan_only'],
            hitl_timeout_seconds=config_data['execution']['hitl_timeout_seconds'],
            hitl_after_plan_generation=config_data['execution']['hitl_after_plan_generation'],
            hitl_after_modified_plan=config_data['execution']['hitl_after_modified_plan'],
            hitl_after_atomizer=config_data['execution']['hitl_after_atomizer'],
            hitl_before_execute=config_data['execution']['hitl_before_execute']
        )
        
        cache_config = CacheConfig(
            enabled=config_data['cache']['enabled'],
            ttl_seconds=config_data['cache']['ttl_seconds'],
            max_size=config_data['cache']['max_size'],
            cache_type=config_data['cache']['cache_type']
        )
        
        # Get default config to use its logging config
        from ...config_utils import auto_load_config
        default_config = auto_load_config()
        
        # Create the main config using the default logging config
        project_config = SentientConfig(
            llm=llm_config,
            execution=execution_config,
            cache=cache_config,
            logging=default_config.logging,  # Use default logging config
            environment=default_config.environment  # Use default environment too
        )
        
        logger.info(f"✅ Created custom project config: {llm_config.provider}/{llm_config.model}, HITL: {execution_config.enable_hitl}")
        return project_config
        
    except Exception as e:
        logger.error(f"Failed to create project config: {e}")
        # Fallback to default config
        from ...config_utils import auto_load_config
        return auto_load_config()
