"""
AggregateHandler - Handles nodes that need aggregation.

This simplified handler focuses solely on aggregation logic,
delegating common functionality to BaseNodeHandler.
"""

from typing import Any, List
from loguru import logger

from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskStatus
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import ContextItem
from .base_handler import BaseNodeHandler, HandlerContext


class AggregateHandler(BaseNodeHandler):
    """
    Handles nodes that need to aggregate results from sub-tasks.
    
    This handler is responsible for:
    - Collecting results from child nodes
    - Filtering redundant information
    - Building aggregation context
    - Executing aggregator agent
    - Synthesizing final result
    """
    
    def __init__(self):
        super().__init__("AggregateHandler")
    
    def _validate_node_state(self, node: TaskNode) -> bool:
        """Validate node is ready for aggregation."""
        return node.status == TaskStatus.AGGREGATING
    
    def _get_stage_name(self) -> str:
        """Get tracing stage name."""
        return "aggregation"
    
    async def _process(self, node: TaskNode, context: HandlerContext) -> Any:
        """
        Main aggregation logic.
        
        Args:
            node: Node to aggregate
            context: Handler context
            
        Returns:
            Aggregated result
        """
        # Collect child results
        child_results = await self._collect_child_results(node, context)
        
        # Build aggregation context with both child results and horizontal dependencies
        aggregation_context = await self._build_aggregation_context(
            node, 
            child_results, 
            context
        )
        
        # Store input for tracing
        node.input_payload_dict = aggregation_context.model_dump()
        
        # Get aggregator agent
        aggregator = await self._get_agent_for_node(node, context, "aggregate")
        if not aggregator:
            raise ValueError(f"No aggregator available for node {node.task_id}")
        
        # Execute aggregation
        logger.info(f"Executing aggregation for node {node.task_id} with {len(child_results)} child results")
        result = await aggregator.process(node, aggregation_context, context.trace_manager)
        
        return result
    
    async def _collect_child_results(
        self, 
        node: TaskNode, 
        context: HandlerContext
    ) -> List[ContextItem]:
        """
        Collect results from child nodes.
        
        Args:
            node: Parent node
            context: Handler context
            
        Returns:
            List of child results as context items
        """
        child_results = []
        
        if not node.sub_graph_id:
            logger.warning(f"Node {node.task_id} has no sub-graph for aggregation")
            return child_results
        
        # Get child nodes from task graph
        # In real implementation, this would come from context.task_graph
        # For now, we'll simulate
        child_nodes = []  # Would be: context.task_graph.get_nodes_in_graph(node.sub_graph_id)
        
        # Filter completed children
        completed_children = [
            child for child in child_nodes
            if child.status in [TaskStatus.DONE, TaskStatus.FAILED]
        ]
        
        # Filter redundant results (in real implementation)
        # This would use DependencyChainTracker
        non_redundant_children = completed_children  # Simplified
        
        logger.info(f"Collecting results from {len(non_redundant_children)} children "
                   f"(filtered from {len(completed_children)} completed)")
        
        # Convert to context items
        for child in non_redundant_children:
            content = child.result if child.status == TaskStatus.DONE else child.error
            
            # Smart content processing based on child type
            processed_content = await self._process_child_content(
                content, 
                child.goal, 
                child.task_type
            )
            
            context_item = ContextItem(
                source_task_id=child.task_id,
                source_task_goal=child.goal,
                content=processed_content,
                content_type_description=f"child_{child.status.value.lower()}_output"
            )
            
            child_results.append(context_item)
        
        return child_results
    
    async def _process_child_content(
        self, 
        content: Any, 
        goal: str, 
        task_type: str
    ) -> str:
        """
        Process child content for aggregation.
        
        Args:
            content: Raw content from child
            goal: Child's goal
            task_type: Child's task type
            
        Returns:
            Processed content string
        """
        if content is None:
            return f"No output for: {goal}"
        
        # Convert to string representation
        if isinstance(content, str):
            text = content
        elif hasattr(content, 'model_dump'):
            text = str(content.model_dump())
        else:
            text = str(content)
        
        # Apply smart sizing based on task type
        max_length = {
            "SEARCH": 2000,
            "THINK": 1500,
            "WRITE": 3000
        }.get(task_type, 1000)
        
        if len(text) > max_length:
            return text[:max_length] + "..."
        
        return text
    
    async def _build_aggregation_context(
        self,
        node: TaskNode,
        child_results: List[ContextItem],
        context: HandlerContext
    ) -> Any:
        """
        Build context for aggregation including both child results
        and horizontal dependencies.
        
        Args:
            node: Node being aggregated
            child_results: Results from children
            context: Handler context
            
        Returns:
            Aggregation context
        """
        # Get base context with horizontal dependencies
        base_context = await self._build_context_for_node(
            node,
            context,
            context_type="aggregation"
        )
        
        # Combine with child results
        if child_results:
            if base_context.relevant_context_items:
                # Add child results to existing context
                base_context.relevant_context_items.extend(child_results)
            else:
                # Just child results
                base_context.relevant_context_items = child_results
            
            # Update formatted context
            formatted_parts = []
            
            # Parent hierarchy first
            if base_context.parent_hierarchy_context:
                formatted_parts.append(base_context.parent_hierarchy_context.formatted_context)
            
            # Horizontal dependencies
            horizontal_items = [
                item for item in base_context.relevant_context_items 
                if item not in child_results
            ]
            if horizontal_items:
                formatted_parts.append("\n=== PREREQUISITE CONTEXT ===")
                for item in horizontal_items:
                    formatted_parts.extend([
                        f"\nSource: {item.source_task_goal}",
                        f"Type: {item.content_type_description}",
                        f"Content: {str(item.content)}",
                        "---"
                    ])
            
            # Child results
            if child_results:
                formatted_parts.append("\n=== CHILD RESULTS ===")
                for item in child_results:
                    formatted_parts.extend([
                        f"\nSource: {item.source_task_goal}",
                        f"Type: {item.content_type_description}",
                        f"Content: {str(item.content)}",
                        "---"
                    ])
            
            base_context.formatted_full_context = "\n".join(formatted_parts)
        
        return base_context
    
    async def _post_process(
        self, 
        node: TaskNode, 
        context: HandlerContext, 
        result: Any
    ):
        """Post-process aggregation result."""
        # Set output type
        node.output_type_description = "aggregated_result"
        
        # Handle the result
        await self._handle_agent_result(
            node,
            result,
            context,
            success_status=TaskStatus.DONE
        )
        
        # Call parent post-process
        await super()._post_process(node, context, result)