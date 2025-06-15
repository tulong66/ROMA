from typing import Dict, Any

class BaseAdapter:
    def _store_execution_details(self, node: 'TaskNode', model_info: Dict[str, Any], 
                               processing_details: Dict[str, Any]):
        """
        Store execution details in node's aux_data for persistence.
        
        Args:
            node: TaskNode to store details for
            model_info: Information about the model used
            processing_details: Details about the processing
        """
        execution_details = {
            'model_info': model_info,
            'processing_started': processing_details.get('processing_started'),
            'processing_completed': processing_details.get('processing_completed'),
            'success': processing_details.get('success', True),
            'system_prompt': processing_details.get('system_prompt'),
            'final_llm_input': processing_details.get('final_llm_input')
        }
        
        # Store in aux_data for persistence
        node.aux_data['execution_details'] = execution_details
        
        # Also store model info separately for easy access
        node.aux_data['model_info'] = model_info 