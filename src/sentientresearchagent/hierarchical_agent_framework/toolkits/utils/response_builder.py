"""Response Builder Utilities
===========================

Standardized response construction for consistent API responses across toolkits.
Provides uniform response formats for success, error, and data storage scenarios.
"""

import time
from typing import Any, Dict, Optional, Union
from pathlib import Path

__all__ = ["ResponseBuilder"]


class ResponseBuilder:
    """Utility class for building standardized API responses.
    
    Provides methods to create consistent response formats across all
    financial and cryptocurrency data toolkits.
    """

    @staticmethod
    def success_response(
        data: Any = None,
        message: str = "Operation completed successfully",
        **additional_fields
    ) -> Dict[str, Any]:
        """Create a standardized success response.
        
        Args:
            data: Response data payload
            message: Success message
            **additional_fields: Additional fields to include in response
            
        Returns:
            dict: Standardized success response
            
        Example:
            >>> ResponseBuilder.success_response(
            ...     data={"price": 50000}, 
            ...     symbol="BTCUSDT",
            ...     market_type="spot"
            ... )
            {
                "success": True,
                "message": "Operation completed successfully",
                "data": {"price": 50000},
                "symbol": "BTCUSDT", 
                "market_type": "spot",
                "fetched_at": 1640995200
            }
        """
        response = {
            "success": True,
            "message": message,
            "fetched_at": int(time.time())
        }
        
        if data is not None:
            response["data"] = data
        
        # Add any additional fields
        response.update(additional_fields)
        
        return response

    @staticmethod
    def error_response(
        message: str,
        error_type: str = "unknown_error",
        details: Optional[Dict[str, Any]] = None,
        **additional_fields
    ) -> Dict[str, Any]:
        """Create a standardized error response.
        
        Args:
            message: Human-readable error message
            error_type: Error classification (e.g., "validation_error", "api_error")
            details: Additional error details
            **additional_fields: Additional fields to include in response
            
        Returns:
            dict: Standardized error response
            
        Example:
            >>> ResponseBuilder.error_response(
            ...     message="Invalid symbol format",
            ...     error_type="validation_error",
            ...     symbol="INVALID"
            ... )
            {
                "success": False,
                "message": "Invalid symbol format",
                "error_type": "validation_error",
                "symbol": "INVALID",
                "timestamp": 1640995200
            }
        """
        response = {
            "success": False,
            "message": message,
            "error_type": error_type,
            "timestamp": int(time.time())
        }
        
        if details:
            response["details"] = details
        
        # Add any additional fields
        response.update(additional_fields)
        
        return response

    @staticmethod
    def data_response(
        data: Any,
        file_path: Optional[Union[str, Path]] = None,
        data_summary: Optional[Dict[str, Any]] = None,
        note: Optional[str] = None,
        **additional_fields
    ) -> Dict[str, Any]:
        """Create a response for data operations with optional file storage.
        
        Args:
            data: Response data (included if file_path is None)  
            file_path: Path to stored data file (if data was stored)
            data_summary: Summary of the data
            note: Additional note about the response
            **additional_fields: Additional fields to include in response
            
        Returns:
            dict: Standardized data response
            
        Example:
            >>> ResponseBuilder.data_response(
            ...     data=None,
            ...     file_path="/data/klines_BTCUSDT_1640995200.parquet",
            ...     data_summary={"size": 5000, "type": "klines"},
            ...     note="Large dataset stored as Parquet file"
            ... )
        """
        response = ResponseBuilder.success_response(**additional_fields)
        
        if file_path:
            response["file_path"] = str(file_path)
            if data_summary:
                response["data_summary"] = data_summary
            if note:
                response["note"] = note
        else:
            response["data"] = data
        
        return response

    @staticmethod
    def build_data_response_with_storage(
        data: Any,
        storage_threshold: int,
        storage_callback: callable,
        filename_template: str,
        large_data_note: str = "Large dataset stored as file",
        **additional_fields
    ) -> Dict[str, Any]:
        """Build response with automatic data storage for large datasets.
        
        Args:
            data: The data to include in response
            storage_threshold: Size threshold for triggering storage
            storage_callback: Function to call for data storage
            filename_template: Template for storage filename
            large_data_note: Note to include when data is stored
            **additional_fields: Additional fields for response
            
        Returns:
            dict: Complete response with data or file path
        """
        # Check if data should be stored
        should_store = False
        
        if hasattr(data, '__len__'):
            should_store = len(data) > storage_threshold
        elif isinstance(data, dict) and 'data' in data:
            if hasattr(data['data'], '__len__'):
                should_store = len(data['data']) > storage_threshold
        
        if should_store:
            try:
                file_path = storage_callback(data, filename_template)
                return ResponseBuilder.data_response(
                    data=None,
                    file_path=file_path,
                    data_summary=ResponseBuilder._get_data_summary(data),
                    note=large_data_note,
                    **additional_fields
                )
            except Exception as e:
                # Fallback to returning data directly if storage fails
                return ResponseBuilder.success_response(
                    data=data,
                    message=f"Data storage failed, returning directly: {str(e)}",
                    **additional_fields
                )
        else:
            return ResponseBuilder.success_response(
                data=data,
                **additional_fields
            )

    @staticmethod
    def validation_error_response(
        field_name: str,
        field_value: Any,
        validation_errors: list,
        **additional_fields
    ) -> Dict[str, Any]:
        """Create a standardized validation error response.
        
        Args:
            field_name: Name of the field that failed validation
            field_value: Value that failed validation
            validation_errors: List of validation error messages
            **additional_fields: Additional fields to include
            
        Returns:
            dict: Standardized validation error response
        """
        return ResponseBuilder.error_response(
            message=f"Validation failed for {field_name}: {', '.join(validation_errors)}",
            error_type="validation_error",
            details={
                "field": field_name,
                "value": field_value,
                "errors": validation_errors
            },
            **additional_fields
        )

    @staticmethod
    def api_error_response(
        api_endpoint: str,
        http_status: Optional[int] = None,
        api_message: Optional[str] = None,
        **additional_fields
    ) -> Dict[str, Any]:
        """Create a standardized API error response.
        
        Args:
            api_endpoint: API endpoint that failed
            http_status: HTTP status code received
            api_message: Original API error message
            **additional_fields: Additional fields to include
            
        Returns:
            dict: Standardized API error response
        """
        message = f"API request failed for {api_endpoint}"
        if http_status:
            message += f" (HTTP {http_status})"
        if api_message:
            message += f": {api_message}"
        
        details = {"endpoint": api_endpoint}
        if http_status:
            details["http_status"] = http_status
        if api_message:
            details["api_message"] = api_message
        
        return ResponseBuilder.error_response(
            message=message,
            error_type="api_error",
            details=details,
            **additional_fields
        )

    @staticmethod
    def _get_data_summary(data: Any) -> Dict[str, Any]:
        """Generate a summary of data for responses.
        
        Args:
            data: Data to summarize
            
        Returns:
            dict: Data summary with size, type, and other metadata
        """
        summary = {
            "type": type(data).__name__,
            "timestamp": int(time.time()),
        }
        
        if hasattr(data, '__len__'):
            summary["size"] = len(data)
            summary["empty"] = len(data) == 0
            
            # For pandas DataFrames
            if hasattr(data, 'columns'):
                summary["columns"] = list(data.columns)
                if hasattr(data, 'memory_usage'):
                    summary["memory_mb"] = round(data.memory_usage(deep=True).sum() / (1024 * 1024), 2)
            
            # For lists of dicts
            elif isinstance(data, list) and data and isinstance(data[0], dict):
                summary["fields"] = list(data[0].keys())
                
        # For nested data structures
        elif isinstance(data, dict):
            summary["keys"] = list(data.keys())
            
            # Check for nested data
            for key, value in data.items():
                if hasattr(value, '__len__'):
                    summary[f"{key}_size"] = len(value)
        
        return summary

    # REMOVED: paginated_response - Not used anywhere in the codebase