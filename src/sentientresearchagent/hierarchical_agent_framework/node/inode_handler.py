from abc import ABC, abstractmethod
from typing import Any # For ProcessorContext initially
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode

class INodeHandler(ABC):
    """
    Abstract base class for node processing handlers (Strategy Pattern).
    """
    @abstractmethod
    async def handle(self, node: TaskNode, processor_context: Any) -> None:
        """
        Handles the processing of a node based on its current state.

        Args:
            node: The TaskNode to process.
            processor_context: An object containing shared resources and components
                               from the NodeProcessor (e.g., task_graph, knowledge_store,
                               config, sub-components like hitl_coordinator).
        """
        pass
