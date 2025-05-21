import networkx as nx
from typing import Dict, List, Optional, Any
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode # Assuming TaskNode is in this path
from enum import Enum # Added for isinstance check
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import CustomSearcherOutput # <--- IMPORT IT
from pydantic import BaseModel # Make sure this import is present
from loguru import logger # Add loguru import

class TaskGraph:
    """Manages the hierarchical graph structure of TaskNodes."""
    def __init__(self):
        # Stores the actual graphs. Key is graph_id, value is nx.DiGraph
        # A graph_id typically corresponds to a parent TaskNode's sub_graph_id or a root_graph_id.
        self.graphs: Dict[str, nx.DiGraph] = {}
        # Flat map for quick node lookup by ID across all graphs
        self.nodes: Dict[str, TaskNode] = {}
        self.root_graph_id: Optional[str] = None
        self.overall_project_goal: Optional[str] = None # Store the main goal

    def add_graph(self, graph_id: str, is_root: bool = False) -> nx.DiGraph:
        if graph_id in self.graphs:
            # In a resumable system, you might load an existing graph.
            # For now, let's assume fresh creation or raise error.
            raise ValueError(f"Graph ID {graph_id} already exists.")
        graph = nx.DiGraph(graph_id=graph_id) # Add graph_id attribute to the graph itself
        self.graphs[graph_id] = graph
        if is_root:
            if self.root_graph_id is not None and self.root_graph_id != graph_id:
                raise ValueError(f"Root graph already set to {self.root_graph_id}. Cannot set {graph_id} as root.")
            self.root_graph_id = graph_id
        logger.info(f"TaskGraph: Added graph '{graph_id}'. Is root: {is_root}")
        return graph

    def get_graph(self, graph_id: str) -> Optional[nx.DiGraph]:
        return self.graphs.get(graph_id)

    def add_node_to_graph(self, graph_id: str, node: TaskNode):
        """Adds a TaskNode to a specific graph and the global node lookup."""
        if graph_id not in self.graphs:
            raise ValueError(f"Graph ID '{graph_id}' not found. Cannot add node '{node.task_id}'.")
        
        graph = self.get_graph(graph_id)
        # The following check is redundant due to the check above and get_graph always returning a graph if the ID exists.
        # if graph is None: # Should be caught by above, but defensive check
        #     raise ValueError(f"Graph object for ID '{graph_id}' is None.")

        if node.task_id in self.nodes:
            # This could happen if a node is part of multiple conceptual graphs,
            # but a TaskNode object should be unique.
            # Or if attempting to re-add. For now, let's enforce uniqueness of add.
            # If updating, use a different method or get_node then modify.
            raise ValueError(f"Node ID {node.task_id} already exists in the global node map.")

        self.nodes[node.task_id] = node
        # Store the TaskNode object itself as a node attribute in the graph
        graph.add_node(node.task_id, task_node_obj=node)
        logger.info(f"TaskGraph: Added node '{node.task_id}' to graph '{graph_id}'.")


    def add_edge(self, graph_id: str, u_node_id: str, v_node_id: str):
        """Adds a directed edge (dependency) between two nodes in a specific graph."""
        graph = self.get_graph(graph_id)
        if not graph:
            raise ValueError(f"Graph ID {graph_id} not found. Cannot add edge between '{u_node_id}' and '{v_node_id}'.")
        if u_node_id not in graph.nodes or v_node_id not in graph.nodes:
            raise ValueError("Nodes must exist in the specified graph to add an edge.")
        graph.add_edge(u_node_id, v_node_id)
        logger.info(f"TaskGraph: Added edge {u_node_id} -> {v_node_id} in graph '{graph_id}'.")

    def get_node(self, node_id: str) -> Optional[TaskNode]:
        """Retrieves a TaskNode by its ID from the global lookup."""
        return self.nodes.get(node_id)

    def get_all_nodes(self) -> List[TaskNode]:
        """Returns a list of all TaskNode objects managed."""
        return list(self.nodes.values())

    def get_node_predecessors(self, graph_id: str, node_id: str) -> List[TaskNode]:
        """Gets all predecessor TaskNodes of a given node within a specific graph."""
        graph = self.get_graph(graph_id)
        if not graph or node_id not in graph:
            return []
        
        predecessor_node_ids = list(graph.predecessors(node_id))
        predecessors = []
        for pred_id in predecessor_node_ids:
            node = self.get_node(pred_id)
            if node:
                predecessors.append(node)
        return predecessors

    def get_node_successors(self, graph_id: str, node_id: str) -> List[TaskNode]:
        """Gets all successor TaskNodes of a given node within a specific graph."""
        graph = self.get_graph(graph_id)
        if not graph or node_id not in graph:
            return []
        
        successor_node_ids = list(graph.successors(node_id))
        successors = []
        for succ_id in successor_node_ids:
            node = self.get_node(succ_id)
            if node:
                successors.append(node)
        return successors

    def get_nodes_in_graph(self, graph_id: str) -> List[TaskNode]:
        """Returns all TaskNodes belonging to a specific graph."""
        graph = self.get_graph(graph_id)
        if not graph:
            return []
        
        node_ids_in_graph = list(graph.nodes())
        nodes = []
        for node_id in node_ids_in_graph:
            node = self.get_node(node_id) # Fetch from the global map
            if node:
                nodes.append(node)
        return nodes

    def to_visualization_dict(self) -> Dict[str, Any]:
        """Serializes the task graph to a dictionary for frontend visualization."""
        output_graphs = {}
        for graph_id, graph_obj in self.graphs.items():
            output_graphs[graph_id] = {
                "nodes": list(graph_obj.nodes()),
                "edges": [{"source": u, "target": v} for u, v in graph_obj.edges()]
            }

        output_nodes = {}
        for node_id, node_obj in self.nodes.items():
            input_context_info_list = []
            # Attempt to extract relevant_context_items
            if node_obj.input_payload_dict and isinstance(node_obj.input_payload_dict, dict):
                # Assuming AgentTaskInput structure where 'relevant_context_items' is a key
                relevant_context = node_obj.input_payload_dict.get('relevant_context_items', [])
                if isinstance(relevant_context, list):
                    for item in relevant_context:
                        if isinstance(item, dict): # Assuming ContextItem structure
                            source_id = item.get('source_task_id')
                            source_goal = item.get('source_task_goal', 'Unknown goal')
                            content_type = item.get('content_type_description', 'Unknown type')
                            if source_id:
                                input_context_info_list.append({
                                    "source_task_id": source_id,
                                    "source_task_goal_summary": source_goal[:50] + "..." if source_goal and len(source_goal) > 50 else source_goal,
                                    "content_type": content_type
                                })
            
            # Simplified input_payload_summary
            input_payload_summary_str = "N/A"
            if node_obj.input_payload_dict:
                keys = list(node_obj.input_payload_dict.keys())
                input_payload_summary_str = f"Input payload with keys: {', '.join(keys)}"

            task_type_val = None
            if node_obj.task_type:
                if isinstance(node_obj.task_type, Enum):
                    task_type_val = node_obj.task_type.value
                else:
                    task_type_val = str(node_obj.task_type)

            node_type_val = None
            if node_obj.node_type:
                if isinstance(node_obj.node_type, Enum):
                    node_type_val = node_obj.node_type.value
                else:
                    node_type_val = str(node_obj.node_type)

            status_val = None
            if node_obj.status:
                if isinstance(node_obj.status, Enum):
                    status_val = node_obj.status.value
                else:
                    status_val = str(node_obj.status)

            processed_result = None
            if node_obj.result is not None:
                if isinstance(node_obj.result, BaseModel):
                    try:
                        processed_result = node_obj.result.model_dump(mode='json')
                    except AttributeError:
                        processed_result = node_obj.result.dict()
                elif isinstance(node_obj.result, (dict, list, str, int, float, bool)):
                    processed_result = node_obj.result
                else:
                    processed_result = str(node_obj.result)

            output_nodes[node_id] = {
                "task_id": node_obj.task_id,
                "goal": node_obj.goal,
                "task_type": task_type_val,
                "node_type": node_type_val,
                "agent_name": node_obj.agent_name,
                "status": status_val,
                "layer": node_obj.layer,
                "parent_node_id": node_obj.parent_node_id,
                "overall_objective": node_obj.overall_objective,
                "output_summary": node_obj.output_summary,
                "full_result": processed_result,
                "error": node_obj.error,
                "sub_graph_id": node_obj.sub_graph_id,
                "planned_sub_task_ids": node_obj.planned_sub_task_ids,
                "input_payload_summary": input_payload_summary_str,
                "input_context_sources": input_context_info_list,
                "timestamp_created": node_obj.timestamp_created.isoformat() if node_obj.timestamp_created else None,
                "timestamp_updated": node_obj.timestamp_updated.isoformat() if node_obj.timestamp_updated else None,
                "timestamp_completed": node_obj.timestamp_completed.isoformat() if node_obj.timestamp_completed else None,
            }

        return {
            "overall_project_goal": self.overall_project_goal,
            "root_graph_id": self.root_graph_id,
            "graphs": output_graphs,
            "all_nodes": output_nodes
        }
