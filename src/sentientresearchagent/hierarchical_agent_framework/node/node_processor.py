from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskStatus, NodeType, TaskType
from sentientresearchagent.hierarchical_agent_framework.graph.task_graph import TaskGraph
from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import KnowledgeStore
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import AgentTaskInput, PlanOutput, AtomizerOutput, ContextItem
from sentientresearchagent.hierarchical_agent_framework.agents.registry import get_agent_adapter
from sentientresearchagent.hierarchical_agent_framework.agents.base_adapter import BaseAdapter # For type hinting
from sentientresearchagent.hierarchical_agent_framework.context.context_builder import resolve_context_for_agent # We'll need to port this

# Basic console coloring for logs
def colored(text, color):
    colors = {"green": "\033[92m", "cyan": "\033[96m", "yellow": "\033[93m", "red": "\033[91m", "bold": "\033[1m", "end": "\033[0m"}
    return f"{colors.get(color, '')}{text}{colors['end']}"

# Configuration
MAX_PLANNING_LAYER = 5 # Max depth for recursive planning

class NodeProcessor:
    """Handles the processing of a single TaskNode's action."""

    def __init__(self):
        # NodeProcessor might not need to store graph_manager or ks if they are passed during process_node
        # However, if context_builder is a member, it might need graph_manager.
        # For now, assuming context_builder will also be instantiated and used locally or passed.
        print("NodeProcessor initialized.")
        # If context_builder becomes complex or needs state, it could be initialized here:
        # self.context_builder = ContextBuilder(task_graph) # If TaskGraph is relatively static or passed on update

    def _create_sub_nodes_from_plan(self, parent_node: TaskNode, plan_output: PlanOutput, task_graph: TaskGraph, knowledge_store: KnowledgeStore):
        """
        Creates TaskNode instances from a plan list, adds them to the graph,
        sets up sequential dependencies, and updates the parent_node.
        """
        if not parent_node.sub_graph_id:
            # This should have been created before calling this function if it's a new plan
            parent_node.sub_graph_id = f"subgraph_{parent_node.task_id}"
            task_graph.add_graph(parent_node.sub_graph_id)
            print(colored(f"    NodeProcessor: Created new subgraph '{parent_node.sub_graph_id}' for parent '{parent_node.task_id}'", "cyan"))
        
        sub_graph_id = parent_node.sub_graph_id
        parent_node.planned_sub_task_ids.clear() # Clear any old sub-tasks if replanning

        created_sub_nodes: list[TaskNode] = []

        for i, sub_task_def in enumerate(plan_output.sub_tasks):
            sub_node_id = f"{parent_node.task_id}.{i+1}" # Simple sequential ID

            try:
                # Validate and convert string types from PlanOutput to Enums for TaskNode
                task_type_enum = TaskType[sub_task_def.task_type.upper()]
                node_type_enum = NodeType[sub_task_def.node_type.upper()]
            except KeyError as e:
                error_msg = f"Invalid task_type or node_type string ('{sub_task_def.task_type}'/'{sub_task_def.node_type}') in plan for parent {parent_node.task_id}: {e}"
                print(colored(f"    NodeProcessor Error: {error_msg}", "red"))
                # Optionally, fail the parent node or skip this sub_task
                # For now, let's skip this potentially invalid sub_task
                continue

            sub_node = TaskNode(
                goal=sub_task_def.goal,
                task_type=task_type_enum,
                node_type=node_type_enum,
                agent_name=sub_task_def.agent_name, # Agent suggestion from planner
                task_id=sub_node_id,
                layer=parent_node.layer + 1,
                parent_node_id=parent_node.task_id,
            )
            created_sub_nodes.append(sub_node)
            task_graph.add_node_to_graph(sub_graph_id, sub_node)
            knowledge_store.add_or_update_record_from_node(sub_node) # Log new sub_node
            parent_node.planned_sub_task_ids.append(sub_node.task_id)
            print(colored(f"      Added sub-node: {sub_node} to graph {sub_graph_id}", "green"))

        # Add sequential dependencies for now
        for i in range(len(created_sub_nodes) - 1):
            u_node = created_sub_nodes[i]
            v_node = created_sub_nodes[i+1]
            task_graph.add_edge(sub_graph_id, u_node.task_id, v_node.task_id)
        
        print(colored(f"    NodeProcessor: Created {len(created_sub_nodes)} sub-nodes for parent {parent_node.task_id}.", "cyan"))


    def _handle_ready_node(self, node: TaskNode, task_graph: TaskGraph, knowledge_store: KnowledgeStore):
        print(colored(f"  NodeProcessor: Handling READY node {node.task_id} (Type: {node.node_type.name}, Goal: '{node.goal[:30]}...')", "yellow"))
        node.update_status(TaskStatus.RUNNING) # Mark as RUNNING before agent call
        knowledge_store.add_or_update_record_from_node(node)

        original_node_type = node.node_type
        
        # 1. Atomicity Check (Conceptual - for now, let's assume an atomizer agent is called)
        # In a full implementation, this would involve:
        # - Getting an 'AtomizerAdapter'.
        # - Preparing AgentTaskInput for the atomizer.
        # - Calling adapter.process() to get AtomizerOutput.
        # - Updating node.goal and node.node_type based on AtomizerOutput.
        
        # --- Simplified Atomicity ---
        # For now, we'll skip explicit atomizer call and proceed based on original node_type
        # or simple rules. A real implementation would use an AtomizerAdapter.
        is_atomic_determined = (original_node_type == NodeType.EXECUTE)
        # If it was planned as EXECUTE, assume it's atomic for now.
        # If it was PLAN, it needs planning unless max depth is reached.

        if original_node_type == NodeType.PLAN and node.layer >= MAX_PLANNING_LAYER:
            print(colored(f"    NodeProcessor: Max planning depth ({MAX_PLANNING_LAYER}) reached for {node.task_id}. Forcing EXECUTE.", "yellow"))
            node.node_type = NodeType.EXECUTE # Change type
            is_atomic_determined = True


        action_to_take = node.node_type # Based on current (possibly atomizer-modified) node_type

        # 2. Prepare AgentTaskInput for the main action (PLAN or EXECUTE)
        # This uses the (potentially updated) node.goal
        agent_task_input = resolve_context_for_agent(
            current_task_id=node.task_id,
            current_goal=node.goal,
            current_task_type=node.task_type.value,
            agent_name=node.agent_name or f"agent_for_{node.task_type.value}", # Placeholder if not set
            knowledge_store=knowledge_store, # Pass the live KnowledgeStore
            overall_project_goal=task_graph.overall_project_goal
        )
        node.input_payload_dict = agent_task_input.model_dump() # Log what the agent will receive

        try:
            if action_to_take == NodeType.PLAN:
                planner_adapter = get_agent_adapter(node, action_verb="plan")
                if not planner_adapter:
                    raise ValueError(f"No PLAN adapter found for node {node.task_id} (Agent: {node.agent_name}, TaskType: {node.task_type.name})")

                print(colored(f"    NodeProcessor: Invoking PLAN adapter '{type(planner_adapter).__name__}' for {node.task_id}", "cyan"))
                plan_output: PlanOutput = planner_adapter.process(node, agent_task_input)

                if not plan_output or not plan_output.sub_tasks:
                    print(colored(f"    NodeProcessor: Planner for {node.task_id} returned no sub-tasks. Converting to EXECUTE.", "yellow"))
                    node.node_type = NodeType.EXECUTE # Convert to execute
                    # Re-prepare context if goal or type changed significantly, for now assume it's fine
                    # Then call the execute logic directly:
                    self._execute_node_action(node, agent_task_input, task_graph, knowledge_store)
                else:
                    self._create_sub_nodes_from_plan(node, plan_output, task_graph, knowledge_store)
                    node.update_status(TaskStatus.PLAN_DONE, result=plan_output.model_dump()) # Store the plan as result
            
            elif action_to_take == NodeType.EXECUTE:
                self._execute_node_action(node, agent_task_input, task_graph, knowledge_store)

            else: # Should not happen if node_type is always PLAN or EXECUTE
                raise ValueError(f"Unexpected node action type: {action_to_take} for node {node.task_id}")

        except Exception as e:
            print(colored(f"  NodeProcessor Error: Failed to process READY node {node.task_id}: {e}", "red"))
            node.update_status(TaskStatus.FAILED, error_msg=str(e))
        
        knowledge_store.add_or_update_record_from_node(node) # Final update for this processing attempt

    def _execute_node_action(self, node: TaskNode, agent_task_input: AgentTaskInput, task_graph: TaskGraph, knowledge_store: KnowledgeStore):
        """Handles the common logic for executing a node, assuming it's NodeType.EXECUTE."""
        executor_adapter = get_agent_adapter(node, action_verb="execute")
        if not executor_adapter:
            raise ValueError(f"No EXECUTE adapter found for node {node.task_id} (Agent: {node.agent_name}, TaskType: {node.task_type.name})")

        print(colored(f"    NodeProcessor: Invoking EXECUTE adapter '{type(executor_adapter).__name__}' for {node.task_id}", "cyan"))
        execution_result = executor_adapter.process(node, agent_task_input)
        
        # Store the result. If Agno returns a Pydantic model, it's stored directly.
        # If it's text, it's stored. Multi-modal refs would also be stored.
        node.output_type_description = f"{type(execution_result).__name__}_result" # Basic type desc
        
        # Check for specific agent signals like "NEEDS_REPLAN"
        # This part is conceptual and depends on how your agents signal this.
        # For example, if the result is a string starting with a special token:
        if isinstance(execution_result, str) and execution_result.startswith("<<NEEDS_REPLAN>>"):
            replan_reason = execution_result.replace("<<NEEDS_REPLAN>>", "").strip()
            print(colored(f"    NodeProcessor: Node {node.task_id} requested REPLAN. Reason: {replan_reason}", "yellow"))
            node.update_status(TaskStatus.NEEDS_REPLAN, result=replan_reason)
        else:
            node.update_status(TaskStatus.DONE, result=execution_result)

    def _handle_aggregating_node(self, node: TaskNode, task_graph: TaskGraph, knowledge_store: KnowledgeStore):
        print(colored(f"  NodeProcessor: Handling AGGREGATING node {node.task_id} (Goal: '{node.goal[:30]}...')", "yellow"))
        node.update_status(TaskStatus.RUNNING) # Mark as RUNNING before agent call
        knowledge_store.add_or_update_record_from_node(node)

        # 1. Prepare AgentTaskInput for the aggregator.
        # The context for an aggregator is typically the results of its children.
        # The `resolve_context_for_agent` should be configured to fetch these.
        # The `current_goal` for the aggregator is the parent (this node's) goal.
        
        # Gather children's results to pass explicitly if `resolve_context_for_agent` doesn't handle it perfectly for aggregators
        # This is a simplified direct gathering; `resolve_context_for_agent` might be more sophisticated.
        child_results_for_aggregator: List[ContextItem] = []
        if node.sub_graph_id:
            child_nodes = task_graph.get_nodes_in_graph(node.sub_graph_id)
            for child_node in child_nodes:
                if child_node.status in [TaskStatus.DONE, TaskStatus.FAILED]:
                    child_results_for_aggregator.append(ContextItem(
                        source_task_id=child_node.task_id,
                        source_task_goal=child_node.goal,
                        content=child_node.result if child_node.status == TaskStatus.DONE else child_node.error,
                        content_type_description=f"child_{child_node.status.value.lower()}_output"
                    ))
        
        agent_task_input = AgentTaskInput(
            current_task_id=node.task_id,
            current_goal=node.goal,
            current_task_type=TaskType.AGGREGATE.value, # Aggregation is a fixed type of action
            relevant_context_items=child_results_for_aggregator, # Pass children's results directly
            overall_project_goal=task_graph.overall_project_goal
        )
        node.input_payload_dict = agent_task_input.model_dump() # Log what aggregator will receive

        try:
            aggregator_adapter = get_agent_adapter(node, action_verb="aggregate")
            if not aggregator_adapter:
                raise ValueError(f"No AGGREGATE adapter found for node {node.task_id}")

            print(colored(f"    NodeProcessor: Invoking AGGREGATE adapter '{type(aggregator_adapter).__name__}' for {node.task_id}", "cyan"))
            aggregated_result = aggregator_adapter.process(node, agent_task_input)
            
            node.output_type_description = "aggregated_text_result" # Assuming text for now
            node.update_status(TaskStatus.DONE, result=aggregated_result)

        except Exception as e:
            print(colored(f"  NodeProcessor Error: Failed to process AGGREGATING node {node.task_id}: {e}", "red"))
            node.update_status(TaskStatus.FAILED, error_msg=str(e))
        
        knowledge_store.add_or_update_record_from_node(node) # Final update


    def process_node(self, node: TaskNode, task_graph: TaskGraph, knowledge_store: KnowledgeStore):
        """
        Processes a node based on its status.
        This method is called by the ExecutionEngine.
        """
        print(colored(f"NodeProcessor: Received node {node.task_id} with status {node.status.name}", "cyan"))
        if node.status == TaskStatus.READY:
            self._handle_ready_node(node, task_graph, knowledge_store)
        elif node.status == TaskStatus.AGGREGATING:
            self._handle_aggregating_node(node, task_graph, knowledge_store)
        else:
            print(colored(f"  NodeProcessor Warning: process_node called on node {node.task_id} with status {node.status.name} - no action taken.", "yellow"))
