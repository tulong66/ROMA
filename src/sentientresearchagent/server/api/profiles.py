"""
Profile Management API Routes

REST endpoints for managing agent profiles.
"""

from flask import jsonify, request
from loguru import logger
from typing import Dict, Any

def create_profile_routes(app, system_manager):
    """
    Create profile management API routes.
    
    Args:
        app: Flask application instance
        system_manager: SystemManager instance
    """
    
    @app.route('/api/profiles', methods=['GET'])
    def get_available_profiles():
        """Get list of available agent profiles."""
        try:
            profiles = system_manager.get_available_profiles()
            current_profile = system_manager.get_current_profile()
            
            # Get details for each profile
            profile_details = []
            for profile_name in profiles:
                details = system_manager.get_profile_details(profile_name)
                details['is_current'] = (profile_name == current_profile)
                profile_details.append(details)
            
            return jsonify({
                "profiles": profile_details,
                "current_profile": current_profile,
                "total_count": len(profiles)
            })
        except Exception as e:
            logger.error(f"Failed to get available profiles: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/profiles/<profile_name>', methods=['GET'])
    def get_profile_details(profile_name: str):
        """Get detailed information about a specific profile."""
        try:
            details = system_manager.get_profile_details(profile_name)
            current_profile = system_manager.get_current_profile()
            details['is_current'] = (profile_name == current_profile)
            
            return jsonify(details)
        except Exception as e:
            logger.error(f"Failed to get profile details for {profile_name}: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/profiles/<profile_name>/switch', methods=['POST'])
    def switch_profile(profile_name: str):
        """Switch to a different agent profile."""
        try:
            logger.info(f"🔄 API request to switch to profile: {profile_name}")
            
            # Perform the switch
            result = system_manager.switch_profile(profile_name)
            
            if result.get("success"):
                logger.info(f"✅ Successfully switched to profile: {profile_name}")
                return jsonify(result)
            else:
                logger.error(f"❌ Failed to switch to profile: {profile_name}")
                return jsonify(result), 400
                
        except Exception as e:
            logger.error(f"Profile switch error for {profile_name}: {e}")
            return jsonify({
                "success": False,
                "error": str(e),
                "profile": profile_name
            }), 500
    
    @app.route('/api/profiles/current', methods=['GET'])
    def get_current_profile():
        """Get information about the currently active profile."""
        try:
            current_profile = system_manager.get_current_profile()
            
            if current_profile:
                details = system_manager.get_profile_details(current_profile)
                details['is_current'] = True
                return jsonify(details)
            else:
                return jsonify({
                    "error": "No profile currently active",
                    "current_profile": None
                }), 404
                
        except Exception as e:
            logger.error(f"Failed to get current profile: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/profiles/validate/<profile_name>', methods=['GET'])
    def validate_profile(profile_name: str):
        """Validate a specific profile without switching to it."""
        try:
            from ....hierarchical_agent_framework.agent_configs.registry_integration import validate_profile
            
            validation = validate_profile(profile_name)
            return jsonify({
                "profile": profile_name,
                "validation": validation,
                "is_valid": validation.get("blueprint_valid", False)
            })
            
        except Exception as e:
            logger.error(f"Profile validation error for {profile_name}: {e}")
            return jsonify({
                "profile": profile_name,
                "error": str(e),
                "is_valid": False
            }), 500 