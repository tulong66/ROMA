from typing import List, Optional, Any, Dict
from pydantic import BaseModel
from loguru import logger

from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskStatus, NodeType, TaskType
from sentientresearchagent.hierarchical_agent_framework.graph.task_graph import TaskGraph
from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import KnowledgeStore
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import (
    AgentTaskInput, PlanOutput, AtomizerOutput, ContextItem,
    PlannerInput, ReplanRequestDetails,
    CustomSearcherOutput, PlanModifierInput
)
from sentientresearchagent.hierarchical_agent_framework.agents.registry import get_agent_adapter, NAMED_AGENTS
from sentientresearchagent.hierarchical_agent_framework.agents.base_adapter import BaseAdapter
# Corrected imports:
from sentientresearchagent.hierarchical_agent_framework.context.context_builder import (
    resolve_context_for_agent
)
from sentientresearchagent.hierarchical_agent_framework.context.planner_context_builder import resolve_input_for_planner_agent
from sentientresearchagent.hierarchical_agent_framework.agents.utils import get_context_summary, TARGET_WORD_COUNT_FOR_CTX_SUMMARIES
from .node_creation_utils import SubNodeCreator
from .node_atomizer_utils import NodeAtomizer
from .node_configs import NodeProcessorConfig
from .hitl_coordinator import HITLCoordinator
from .inode_handler import INodeHandler
from .node_handlers import (
    ReadyPlanHandler,
    ReadyExecuteHandler,
    ReadyNodeHandler,
    AggregatingNodeHandler,
    NeedsReplanNodeHandler
)


MAX_PLANNING_LAYER = 2 # This seems to be a global constant, consider moving to config
MAX_REPLAN_ATTEMPTS = 1 # This seems to be a global constant, consider moving to config


class ProcessorContext:
    """Holds shared resources and configurations for node handlers."""
    def __init__(self,
                 task_graph: TaskGraph,
                 knowledge_store: KnowledgeStore,
                 config: NodeProcessorConfig,
                 hitl_coordinator: HITLCoordinator,
                 sub_node_creator: SubNodeCreator,
                 node_atomizer: NodeAtomizer):
        self.task_graph = task_graph
        self.knowledge_store = knowledge_store
        self.config = config
        self.hitl_coordinator = hitl_coordinator
        self.sub_node_creator = sub_node_creator
        self.node_atomizer = node_atomizer


class NodeProcessor:
    """
    Orchestrates the processing of a TaskNode by delegating to appropriate handlers
    based on the node's status and type.
    """

    def __init__(self,
                 task_graph: TaskGraph,
                 knowledge_store: KnowledgeStore,
                 config: Optional[NodeProcessorConfig] = None):
        logger.info("NodeProcessor initialized.")
        self.config = config if config else NodeProcessorConfig()
        self.task_graph = task_graph
        self.knowledge_store = knowledge_store
        
        self.hitl_coordinator = HITLCoordinator(self.config)
        self.sub_node_creator = SubNodeCreator(task_graph, knowledge_store)
        # Assuming NodeAtomizer's constructor was updated to take hitl_coordinator directly
        self.node_atomizer = NodeAtomizer(self.hitl_coordinator)

        # Create the context object that handlers will use
        self.processor_context = ProcessorContext(
            task_graph=self.task_graph,
            knowledge_store=self.knowledge_store,
            config=self.config,
            hitl_coordinator=self.hitl_coordinator,
            sub_node_creator=self.sub_node_creator,
            node_atomizer=self.node_atomizer
        )

        # Instantiate handlers
        _ready_plan_handler = ReadyPlanHandler()
        _ready_execute_handler = ReadyExecuteHandler()

        # Setup strategy mapping for handlers
        self.handler_strategies: Dict[TaskStatus, INodeHandler] = {
            TaskStatus.READY: ReadyNodeHandler(_ready_plan_handler, _ready_execute_handler),
            TaskStatus.AGGREGATING: AggregatingNodeHandler(),
            TaskStatus.NEEDS_REPLAN: NeedsReplanNodeHandler()
        }
        logger.info(f"NodeProcessor initialized with handlers for statuses: {list(self.handler_strategies.keys())}")


    async def process_node(self, node: TaskNode, task_graph: TaskGraph, knowledge_store: KnowledgeStore):
        """
        Processes a node based on its current status using a strategy pattern.
        """
        self.processor_context.task_graph = task_graph
        self.processor_context.knowledge_store = knowledge_store
        
        original_status = node.status

        logger.info(f"NodeProcessor: Processing node {node.task_id} (Status: {node.status.name}, Type: {node.node_type}, Goal: '{node.goal[:30]}...')")
        
        handler = self.handler_strategies.get(node.status)

        if handler:
            try:
                await handler.handle(node, self.processor_context)
            except Exception as e:
                logger.exception(f"Node {node.task_id}: Unhandled exception in {handler.__class__.__name__}: {e}")
                if node.status not in [TaskStatus.FAILED, TaskStatus.CANCELLED]:
                    node.update_status(TaskStatus.FAILED, error_msg=f"Error in {handler.__class__.__name__}: {str(e)}")
        else:
            logger.warning(f"Node {node.task_id}: No specific handler for status {node.status.name}. Node will not be processed further in this cycle unless status changes.")

        if node.status != original_status or node.result is not None or node.error is not None:
             logger.info(f"Node {node.task_id} status changed from {original_status} to {node.status} or has new results/errors. Updating knowledge store.")
        
        self.knowledge_store.add_or_update_record_from_node(node)
        logger.info(f"NodeProcessor: Finished processing for node {node.task_id}. Final status: {node.status.name}")