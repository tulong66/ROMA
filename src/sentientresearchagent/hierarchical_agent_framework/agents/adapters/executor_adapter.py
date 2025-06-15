from datetime import datetime

class ExecutorAdapter:
    def process(self, node, context):
        # Existing code...

        # Store execution details for persistence
        self._store_execution_details(node, {
            'adapter_name': self.agent_name,
            'model_provider': getattr(self.agent, 'model_provider', 'unknown'),
            'model_name': getattr(self.agent, 'model_name', 'unknown'),
            'model_id': getattr(self.agent, 'model_id', 'unknown')
        }, {
            'processing_started': datetime.now().isoformat(),
            'processing_completed': datetime.now().isoformat(),
            'success': True,
            'system_prompt': getattr(context, 'system_prompt', None),
            'final_llm_input': getattr(context, 'final_llm_input', None)
        }) 