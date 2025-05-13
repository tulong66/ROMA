from typing import Optional
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskStatus, NodeType
from sentientresearchagent.hierarchical_agent_framework.graph.task_graph import TaskGraph # Adjusted import
from collections import deque # Keep deque for graph traversal if needed for finding container graph

class StateManager:
    """Handles logic for checking if nodes can transition state."""

    def __init__(self, task_graph: TaskGraph):
        self.task_graph = task_graph

    def _find_container_graph_id_for_node(self, node: TaskNode) -> Optional[str]:
        """
        Helper to find which graph contains a node.
        A node lives in the sub_graph of its parent.
        If no parent, it's in the root graph.
        """
        if node.parent_node_id:
            parent_node = self.task_graph.get_node(node.parent_node_id)
            if parent_node:
                # The node is in the sub-graph created and managed by its parent
                return parent_node.sub_graph_id
            else:
                # This case (parent_node_id exists but parent_node not found) is an inconsistency.
                print(f"StateManager Warning: Node {node.task_id} has parent_id {node.parent_node_id} but parent not found.")
                return None 
        elif self.task_graph.root_graph_id and node.task_id in self.task_graph.get_graph(self.task_graph.root_graph_id).nodes:
            # If it has no parent, it should be in the root graph.
            return self.task_graph.root_graph_id
        else:
            # Fallback: if root_graph_id is not set or node not in root (should not happen for root nodes)
            # This could also be an error condition or indicate a detached node.
            # For now, let's try searching all graphs if the above heuristics fail.
            # This is less efficient and ideally shouldn't be needed if graph structure is consistent.
            print(f"StateManager Warning: Node {node.task_id} container graph not found by parent/root heuristic. Searching all graphs.")
            for graph_id, graph_obj in self.task_graph.graphs.items():
                if node.task_id in graph_obj.nodes:
                    return graph_id
            print(f"StateManager Error: Node {node.task_id} could not be located in any graph.")
            return None


    def can_become_ready(self, node: TaskNode) -> bool:
        """Checks if a PENDING node can transition to READY."""
        if node.status != TaskStatus.PENDING:
            return False

        # 1. Check parent status (must be RUNNING/PLAN_DONE or it's a root node with no parent)
        parent_conditions_met = False
        if node.parent_node_id:
            parent_node = self.task_graph.get_node(node.parent_node_id)
            if parent_node and parent_node.status in (TaskStatus.RUNNING, TaskStatus.PLAN_DONE):
                parent_conditions_met = True
            # If parent exists but is not in a runnable state, this node cannot become ready
        else: # Root node case (no parent_node_id)
            parent_conditions_met = True

        if not parent_conditions_met:
            # print(f"Node {node.task_id} cannot become READY: Parent conditions not met.")
            return False

        # 2. Determine the graph this node belongs to.
        #    A node belongs to the sub-graph created by its parent, or the root graph if it's a root node.
        container_graph_id = self._find_container_graph_id_for_node(node)
        
        if not container_graph_id:
            print(f"Node {node.task_id} cannot become READY: Cannot determine its container graph.")
            return False
        
        # 3. Check dependencies (predecessors) within its own graph.
        #    All direct predecessors in its container graph must be DONE.
        predecessors = self.task_graph.get_node_predecessors(container_graph_id, node.task_id)
        if not predecessors: # No predecessors, so dependency condition is met
            # print(f"Node {node.task_id} can become READY: Parent OK, No predecessors.")
            return True
        
        deps_done = all(pred.status == TaskStatus.DONE for pred in predecessors)
        # if deps_done:
        #     print(f"Node {node.task_id} can become READY: Parent OK, Predecessors DONE.")
        # else:
        #     print(f"Node {node.task_id} cannot become READY: Not all predecessors are DONE.")
        return deps_done

    def can_aggregate(self, node: TaskNode) -> bool:
        """Checks if a PLAN_DONE node (which is a PLAN type node) can transition to AGGREGATING."""
        if node.status != TaskStatus.PLAN_DONE or node.node_type != NodeType.PLAN: # Ensure it's a PLAN node
            return False
        
        # It must have created a sub-graph where its children tasks reside
        if not node.sub_graph_id:
            # This would be an inconsistent state for a PLAN_DONE node.
            # A PLAN node at PLAN_DONE should always have a sub_graph_id.
            print(f"StateManager Warning: Node {node.task_id} is PLAN_DONE but has no sub_graph_id.")
            return False

        # All tasks within its sub_graph_id must be in a terminal state (DONE or FAILED).
        # These are the tasks that were generated by this PLAN node.
        sub_graph_nodes = self.task_graph.get_nodes_in_graph(node.sub_graph_id)
        
        if not sub_graph_nodes:
            # If a plan resulted in no sub-tasks, it could be considered ready to "aggregate" nothing.
            # This means the plan was effectively atomic or led to an empty plan.
            # The aggregator agent will have to handle an empty set of child results.
            print(f"Node {node.task_id} can AGGREGATE: PLAN_DONE and its sub-graph '{node.sub_graph_id}' is empty.")
            return True

        all_sub_finished = all(
            sn.status in (TaskStatus.DONE, TaskStatus.FAILED) for sn in sub_graph_nodes
        )
        # if all_sub_finished:
        #     print(f"Node {node.task_id} can AGGREGATE: All {len(sub_graph_nodes)} sub-tasks in '{node.sub_graph_id}' are finished.")
        # else:
        #     print(f"Node {node.task_id} cannot AGGREGATE: Not all sub-tasks in '{node.sub_graph_id}' are finished.")
        return all_sub_finished