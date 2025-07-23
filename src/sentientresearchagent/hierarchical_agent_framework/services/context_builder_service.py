"""
ContextBuilderService - Centralized context building service.

This service consolidates all context building logic,
making it easier to understand and modify how context is assembled.
"""

from typing import Optional, Dict, Any, List, TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum
from loguru import logger

from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskType
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import (
    AgentTaskInput, ContextItem, ParentHierarchyContext
)

if TYPE_CHECKING:
    from sentientresearchagent.hierarchical_agent_framework.graph.task_graph import TaskGraph
    from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import KnowledgeStore


class ContextType(Enum):
    """Types of context to build."""
    DEFAULT = "default"
    PLANNING = "planning"
    EXECUTION = "execution"
    AGGREGATION = "aggregation"
    ATOMIZATION = "atomization"
    MODIFICATION = "modification"


@dataclass
class ContextConfig:
    """Configuration for context building."""
    max_context_length: int = 10000
    include_parent_hierarchy: bool = True
    include_horizontal_dependencies: bool = True
    include_similar_tasks: bool = True
    max_similar_tasks: int = 5
    summarize_long_content: bool = True
    target_summary_words: int = 150


class ContextBuilderService:
    """
    Service for building context for agent tasks.
    
    This service:
    - Centralizes context building logic
    - Provides different context types for different purposes
    - Manages context size and relevance
    - Supports custom context strategies
    """
    
    def __init__(self, config: Optional[ContextConfig] = None):
        """
        Initialize the ContextBuilderService.
        
        Args:
            config: Context building configuration
        """
        self.config = config or ContextConfig()
        
        # Context building strategies
        self._strategies = {
            ContextType.DEFAULT: self._build_default_context,
            ContextType.PLANNING: self._build_planning_context,
            ContextType.EXECUTION: self._build_execution_context,
            ContextType.AGGREGATION: self._build_aggregation_context,
            ContextType.ATOMIZATION: self._build_atomization_context,
            ContextType.MODIFICATION: self._build_modification_context,
        }
        
        # Metrics
        self._metrics = {
            "contexts_built": 0,
            "average_context_size": 0,
            "contexts_by_type": {}
        }
        
        logger.info("ContextBuilderService initialized")
    
    async def build_context(
        self,
        node: TaskNode,
        context_type: str,
        knowledge_store: "KnowledgeStore",
        task_graph: Optional["TaskGraph"] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> AgentTaskInput:
        """
        Build context for a node.
        
        Args:
            node: Node needing context
            context_type: Type of context to build
            knowledge_store: Knowledge store for retrieving context
            task_graph: Task graph for hierarchy information
            additional_context: Additional context to include
            
        Returns:
            Built context
        """
        # Convert string to enum
        try:
            context_enum = ContextType(context_type)
        except ValueError:
            logger.warning(f"Unknown context type: {context_type}, using default")
            context_enum = ContextType.DEFAULT
        
        # Update metrics
        self._metrics["contexts_built"] += 1
        self._metrics["contexts_by_type"][context_enum.value] = \
            self._metrics["contexts_by_type"].get(context_enum.value, 0) + 1
        
        # Get strategy
        strategy = self._strategies.get(context_enum, self._build_default_context)
        
        # Build context
        try:
            context = await strategy(node, knowledge_store, task_graph, additional_context)
            
            # Update average size
            self._update_average_size(len(context.formatted_full_context or ""))
            
            return context
            
        except Exception as e:
            logger.error(f"Failed to build {context_type} context for {node.task_id}: {e}")
            # Return minimal context on error
            return self._build_minimal_context(node)
    
    async def _build_default_context(
        self,
        node: TaskNode,
        knowledge_store: "KnowledgeStore",
        task_graph: Optional["TaskGraph"],
        additional_context: Optional[Dict[str, Any]]
    ) -> AgentTaskInput:
        """Build default context with all relevant information."""
        context_items = []
        
        # 1. Parent hierarchy context
        parent_context = None
        if self.config.include_parent_hierarchy and task_graph:
            parent_context = await self._build_parent_hierarchy(node, task_graph, knowledge_store)
        
        # 2. Horizontal dependencies
        if self.config.include_horizontal_dependencies and knowledge_store:
            dep_items = await self._get_dependency_context(node, knowledge_store)
            context_items.extend(dep_items)
        
        # 3. Similar completed tasks
        if self.config.include_similar_tasks and knowledge_store:
            similar_items = await self._get_similar_task_context(node, knowledge_store)
            context_items.extend(similar_items)
        
        # 4. Additional context
        if additional_context:
            for key, value in additional_context.items():
                context_items.append(ContextItem(
                    source_task_id=f"additional_{key}",
                    source_task_goal=f"Additional context: {key}",
                    content=str(value),
                    content_type_description="additional_context"
                ))
        
        # Format context
        formatted_context = self._format_context(parent_context, context_items)
        
        # Build final input
        return AgentTaskInput(
            current_task_id=node.task_id,
            current_goal=node.goal,
            current_task_type=str(node.task_type),
            parent_hierarchy_context=parent_context,
            relevant_context_items=context_items if context_items else None,
            formatted_full_context=formatted_context,
            overall_project_goal=task_graph.overall_project_goal if task_graph else None
        )
    
    async def _build_planning_context(
        self,
        node: TaskNode,
        knowledge_store: "KnowledgeStore",
        task_graph: Optional["TaskGraph"],
        additional_context: Optional[Dict[str, Any]]
    ) -> AgentTaskInput:
        """Build context optimized for planning."""
        # Start with default context
        context = await self._build_default_context(node, knowledge_store, task_graph, additional_context)
        
        # Add planning-specific elements
        if knowledge_store:
            # Get successful plans from similar tasks
            similar_plans = await self._get_similar_plans(node, knowledge_store)
            if similar_plans:
                plan_items = [
                    ContextItem(
                        source_task_id=plan["task_id"],
                        source_task_goal=plan["goal"],
                        content=f"Successful plan: {plan['summary']}",
                        content_type_description="similar_plan"
                    )
                    for plan in similar_plans[:3]
                ]
                if context.relevant_context_items:
                    context.relevant_context_items.extend(plan_items)
                else:
                    context.relevant_context_items = plan_items
        
        return context
    
    async def _build_execution_context(
        self,
        node: TaskNode,
        knowledge_store: "KnowledgeStore",
        task_graph: Optional["TaskGraph"],
        additional_context: Optional[Dict[str, Any]]
    ) -> AgentTaskInput:
        """Build context optimized for execution."""
        # Start with default context
        context = await self._build_default_context(node, knowledge_store, task_graph, additional_context)
        
        # Prioritize recent, relevant results
        if context.relevant_context_items:
            # Sort by relevance and recency
            context.relevant_context_items.sort(
                key=lambda x: (
                    x.content_type_description == "prerequisite",
                    x.source_task_id.startswith("recent_")
                ),
                reverse=True
            )
            
            # Limit context size more aggressively for execution
            max_items = 10
            if len(context.relevant_context_items) > max_items:
                context.relevant_context_items = context.relevant_context_items[:max_items]
        
        return context
    
    async def _build_aggregation_context(
        self,
        node: TaskNode,
        knowledge_store: "KnowledgeStore",
        task_graph: Optional["TaskGraph"],
        additional_context: Optional[Dict[str, Any]]
    ) -> AgentTaskInput:
        """Build context optimized for aggregation."""
        # For aggregation, we primarily need parent context and horizontal dependencies
        # Child results are added separately by the aggregate handler
        context_items = []
        
        # Parent hierarchy is crucial for aggregation
        parent_context = None
        if task_graph:
            parent_context = await self._build_parent_hierarchy(node, task_graph, knowledge_store)
        
        # Horizontal dependencies
        if knowledge_store:
            dep_items = await self._get_dependency_context(node, knowledge_store)
            context_items.extend(dep_items)
        
        # Format context
        formatted_context = self._format_context(parent_context, context_items)
        
        return AgentTaskInput(
            current_task_id=node.task_id,
            current_goal=node.goal,
            current_task_type="AGGREGATE",
            parent_hierarchy_context=parent_context,
            relevant_context_items=context_items if context_items else None,
            formatted_full_context=formatted_context,
            overall_project_goal=task_graph.overall_project_goal if task_graph else None
        )
    
    async def _build_atomization_context(
        self,
        node: TaskNode,
        knowledge_store: "KnowledgeStore",
        task_graph: Optional["TaskGraph"],
        additional_context: Optional[Dict[str, Any]]
    ) -> AgentTaskInput:
        """Build context optimized for atomization decisions."""
        # Minimal context for atomization
        parent_context = None
        if task_graph and node.parent_node_id:
            parent = task_graph.get_node(node.parent_node_id)
            if parent:
                parent_context = ParentHierarchyContext(
                    parent_goal=parent.goal,
                    parent_task_type=str(parent.task_type),
                    formatted_context=f"Parent task: {parent.goal}"
                )
        
        formatted_context = f"Task: {node.goal}\nLayer: {node.layer}"
        if parent_context:
            formatted_context = f"{parent_context.formatted_context}\n{formatted_context}"
        
        return AgentTaskInput(
            current_task_id=node.task_id,
            current_goal=node.goal,
            current_task_type=str(node.task_type),
            parent_hierarchy_context=parent_context,
            relevant_context_items=None,
            formatted_full_context=formatted_context,
            overall_project_goal=task_graph.overall_project_goal if task_graph else None
        )
    
    async def _build_modification_context(
        self,
        node: TaskNode,
        knowledge_store: "KnowledgeStore",
        task_graph: Optional["TaskGraph"],
        additional_context: Optional[Dict[str, Any]]
    ) -> AgentTaskInput:
        """Build context for plan modification."""
        # Start with planning context
        context = await self._build_planning_context(node, knowledge_store, task_graph, additional_context)
        
        # Add modification-specific data from additional_context
        if additional_context:
            mod_items = []
            
            if "original_plan" in additional_context:
                mod_items.append(ContextItem(
                    source_task_id="original_plan",
                    source_task_goal="Original plan to modify",
                    content=str(additional_context["original_plan"]),
                    content_type_description="original_plan"
                ))
            
            if "modification_instructions" in additional_context:
                mod_items.append(ContextItem(
                    source_task_id="modification_request",
                    source_task_goal="Modification instructions",
                    content=additional_context["modification_instructions"],
                    content_type_description="user_instructions"
                ))
            
            if mod_items:
                if context.relevant_context_items:
                    context.relevant_context_items = mod_items + context.relevant_context_items
                else:
                    context.relevant_context_items = mod_items
        
        return context
    
    async def _build_parent_hierarchy(
        self,
        node: TaskNode,
        task_graph: "TaskGraph",
        knowledge_store: "KnowledgeStore"
    ) -> Optional[ParentHierarchyContext]:
        """Build parent hierarchy context."""
        if not node.parent_node_id:
            return None
        
        parent = task_graph.get_node(node.parent_node_id)
        if not parent:
            return None
        
        # Get parent's context recursively (limited depth)
        hierarchy_parts = []
        current = parent
        depth = 0
        max_depth = 3
        
        while current and depth < max_depth:
            summary = current.output_summary or current.goal
            hierarchy_parts.append(f"L{current.layer}: {summary}")
            
            if current.parent_node_id:
                current = task_graph.get_node(current.parent_node_id)
                depth += 1
            else:
                break
        
        # Format hierarchy
        hierarchy_parts.reverse()
        formatted = "\n".join(hierarchy_parts)
        
        return ParentHierarchyContext(
            parent_goal=parent.goal,
            parent_task_type=str(parent.task_type),
            formatted_context=formatted
        )
    
    async def _get_dependency_context(
        self,
        node: TaskNode,
        knowledge_store: "KnowledgeStore"
    ) -> List[ContextItem]:
        """Get context from dependencies."""
        # In real implementation, would query knowledge store
        # for completed prerequisite tasks
        return []
    
    async def _get_similar_task_context(
        self,
        node: TaskNode,
        knowledge_store: "KnowledgeStore"
    ) -> List[ContextItem]:
        """Get context from similar completed tasks."""
        # In real implementation, would use semantic search
        # to find similar completed tasks
        return []
    
    async def _get_similar_plans(
        self,
        node: TaskNode,
        knowledge_store: "KnowledgeStore"
    ) -> List[Dict[str, Any]]:
        """Get successful plans from similar tasks."""
        # In real implementation, would search for similar
        # tasks that were successfully planned
        return []
    
    def _format_context(
        self,
        parent_context: Optional[ParentHierarchyContext],
        context_items: List[ContextItem]
    ) -> str:
        """Format context into a string."""
        parts = []
        
        if parent_context:
            parts.append("=== PARENT HIERARCHY ===")
            parts.append(parent_context.formatted_context)
            parts.append("")
        
        if context_items:
            parts.append("=== RELEVANT CONTEXT ===")
            for item in context_items:
                parts.append(f"\nSource: {item.source_task_goal}")
                parts.append(f"Type: {item.content_type_description}")
                
                # Summarize long content if needed
                content = str(item.content)
                if self.config.summarize_long_content and len(content) > 500:
                    content = content[:500] + "..."
                
                parts.append(f"Content: {content}")
                parts.append("---")
        
        formatted = "\n".join(parts)
        
        # Enforce max length
        if len(formatted) > self.config.max_context_length:
            formatted = formatted[:self.config.max_context_length] + "\n... [truncated]"
        
        return formatted
    
    def _build_minimal_context(self, node: TaskNode) -> AgentTaskInput:
        """Build minimal context as fallback."""
        return AgentTaskInput(
            current_task_id=node.task_id,
            current_goal=node.goal,
            current_task_type=str(node.task_type),
            parent_hierarchy_context=None,
            relevant_context_items=None,
            formatted_full_context=f"Task: {node.goal}",
            overall_project_goal=None
        )
    
    def _update_average_size(self, size: int):
        """Update average context size metric."""
        current_avg = self._metrics["average_context_size"]
        total_built = self._metrics["contexts_built"]
        
        self._metrics["average_context_size"] = (
            (current_avg * (total_built - 1) + size) / total_built
        )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get context building metrics."""
        return self._metrics.copy()
    
    def update_config(self, new_config: ContextConfig):
        """Update context building configuration."""
        self.config = new_config
        logger.info("ContextBuilderService config updated")