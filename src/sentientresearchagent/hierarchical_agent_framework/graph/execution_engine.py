from sentientresearchagent.hierarchical_agent_framework.graph.task_graph import TaskGraph
# NodeProcessor will be defined later, so we use a forward reference or Any for now
# from sentientresearchagent.hierarchical_agent_framework.node.node_processor import NodeProcessor
from typing import Any as NodeProcessorType # Placeholder for NodeProcessor
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskStatus, NodeType, TaskType
from sentientresearchagent.hierarchical_agent_framework.graph.state_manager import StateManager
from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import KnowledgeStore # For logging to KS

from typing import Optional, Callable
import pprint # For logging results

# Basic console coloring for logs, can be replaced with a proper logger
def colored(text, color):
    # Simple implementation, replace with a library like 'termcolor' if needed
    colors = {"green": "\033[92m", "cyan": "\033[96m", "yellow": "\033[93m", "red": "\033[91m", "bold": "\033[1m", "end": "\033[0m"}
    return f"{colors.get(color, '')}{text}{colors['end']}"


class ExecutionEngine:
    """Orchestrates the overall execution flow of tasks in the graph."""

    def __init__(self, 
                 task_graph: TaskGraph,
                 node_processor: NodeProcessorType, # Actual NodeProcessor instance
                 state_manager: StateManager,
                 knowledge_store: KnowledgeStore): # Added KnowledgeStore
        self.task_graph = task_graph
        self.node_processor = node_processor
        self.state_manager = state_manager
        self.knowledge_store = knowledge_store # Store KS
        # self.node_processor.set_viz_handler(viz_handler) # If you re-add visualization

    def initialize_project(self, 
                           root_goal: str, 
                           root_task_type: TaskType = TaskType.WRITE, # Default, can be changed
                           initial_agent_name: Optional[str] = "default_planner" # Agent for the root
                          ):
        """Sets up the initial root node for the project."""
        if self.task_graph.root_graph_id is not None:
            print(colored("CONSOLE LOG: Project already initialized or root graph exists.", "yellow"))
            # Potentially load existing state or raise error
            return

        self.task_graph.overall_project_goal = root_goal
        
        root_node_id = "root" # Fixed ID for the ultimate root task
        root_graph_id = "root_graph" # Graph containing the root task

        # The root task usually starts as a PLAN to decompose the overall goal
        root_node = TaskNode(
            goal=root_goal,
            task_type=root_task_type, # This might often be a general "project" type
            node_type=NodeType.PLAN,  # Root usually starts by planning
            agent_name=initial_agent_name, # Agent responsible for decomposing the root goal
            layer=0,
            task_id=root_node_id
        )
        
        self.task_graph.add_graph(root_graph_id, is_root=True)
        self.task_graph.add_node_to_graph(root_graph_id, root_node)
        self.knowledge_store.add_or_update_record_from_node(root_node) # Log initial node

        # if self.viz_handler: ...

        print(colored(f"CONSOLE LOG: Initialized with root node: {root_node.task_id} in graph {root_graph_id}", "green"))

    def run_cycle(self, max_steps: int = 50):
        """Runs the execution loop for a specified number of steps or until completion/deadlock."""
        print(colored("CONSOLE LOG: \n--- Starting Execution Cycle ---", "cyan"))
        
        if not self.task_graph.root_graph_id or not self.task_graph.get_node("root"):
            print(colored("CONSOLE LOG: Project not initialized. Please call initialize_project first.", "red"))
            return None

        for step in range(max_steps):
            print(colored(f"\nCONSOLE LOG: --- Step {step + 1} of {max_steps} ---", "cyan"))
            processed_in_step = False
            
            all_nodes = self.task_graph.get_all_nodes()
            if not all_nodes:
                print(colored("CONSOLE LOG: No nodes in the graph to process.", "yellow"))
                break

            # --- 1. Update PENDING -> READY transitions ---
            for node in all_nodes:
                if node.status == TaskStatus.PENDING:
                    if self.state_manager.can_become_ready(node):
                        node.update_status(TaskStatus.READY)
                        self.knowledge_store.add_or_update_record_from_node(node) # Update KS
                        processed_in_step = True
                        print(colored(f"  Transition: Node {node.task_id} PENDING -> READY", "green"))


            # --- 2. Process one READY or AGGREGATING node ---
            # Prioritize AGGREGATING nodes to free up parent PLAN nodes sooner
            # Then process READY nodes. Could be more sophisticated (e.g., by layer).
            
            node_to_process = next((n for n in all_nodes if n.status == TaskStatus.AGGREGATING), None)
            if not node_to_process:
                node_to_process = next((n for n in all_nodes if n.status == TaskStatus.READY), None)

            if node_to_process:
                print(colored(f"  Processing Node: {node_to_process.task_id} (Status: {node_to_process.status.name}, Layer: {node_to_process.layer})", "yellow"))
                
                # NodeProcessor will handle changing status to RUNNING, and then to its outcome.
                self.node_processor.process_node(node_to_process, self.task_graph, self.knowledge_store)
                # After processing, node status and KS record are updated by NodeProcessor
                
                processed_in_step = True
                # After a node is processed, its state (and potentially others) might change,
                # so we continue to the next step to re-evaluate.
                # The node_processor should update the node's status (e.g. to RUNNING, then to PLAN_DONE/DONE/FAILED)
                # and log to knowledge_store.
                continue 

            # --- 3. Update PLAN_DONE -> AGGREGATING transitions ---
            # This check should happen *after* an attempt to process READY/AGGREGATING nodes
            # because a PLAN node might have just become PLAN_DONE in the current step.
            for node in all_nodes:
                if node.status == TaskStatus.PLAN_DONE: # Only PLAN type nodes go to PLAN_DONE
                    if self.state_manager.can_aggregate(node):
                        node.update_status(TaskStatus.AGGREGATING)
                        self.knowledge_store.add_or_update_record_from_node(node) # Update KS
                        processed_in_step = True
                        print(colored(f"  Transition: Node {node.task_id} PLAN_DONE -> AGGREGATING", "green"))

            # --- Check for completion or deadlock ---
            active_statuses = {TaskStatus.PENDING, TaskStatus.READY, TaskStatus.RUNNING, TaskStatus.PLAN_DONE, TaskStatus.AGGREGATING}
            # Re-fetch all_nodes as their statuses might have changed
            all_nodes = self.task_graph.get_all_nodes()
            if not any(n.status in active_statuses for n in all_nodes):
                print(colored("CONSOLE LOG: \n--- Execution Finished: No active nodes left. ---", "green"))
                break

            if not processed_in_step and any(n.status in active_statuses for n in all_nodes):
                print(colored("CONSOLE LOG: \n--- Execution Halted: No progress made in this step. Possible deadlock or incomplete logic. ---", "red"))
                # You might want to log current states of all active nodes here for debugging
                for n in all_nodes:
                    if n.status in active_statuses:
                        print(colored(f"    - Active: {n.task_id}, Status: {n.status.name}, Goal: '{n.goal[:50]}...'", "red"))
                break
        
        if step == max_steps -1 and any(n.status in active_statuses for n in self.task_graph.get_all_nodes()):
            print(colored("CONSOLE LOG: \n--- Execution Finished: Reached max steps. ---", "yellow"))

        # Print final results
        self._log_final_statuses()
        
        root_node_final = self.task_graph.get_node("root")
        if root_node_final:
            print(colored(f"CONSOLE LOG: \nRoot Task ('{root_node_final.goal}') Final Result:", "green"))
            pprint.pprint(root_node_final.result)
            return root_node_final.result
        return None

    def _log_final_statuses(self):
        print(colored("CONSOLE LOG: \n--- Final Node Statuses & Results ---", "cyan"))
        all_final_nodes = sorted(self.task_graph.get_all_nodes(), key=lambda n: (n.layer, n.task_id))
        for node in all_final_nodes:
            status_color = "green" if node.status == TaskStatus.DONE else ("red" if node.status == TaskStatus.FAILED else "yellow")
            status_str = colored(f"{node.status.name}", status_color)
            if node.status == TaskStatus.FAILED and node.error:
                 status_str += colored(f" (Error: {node.error})", "red")
            
            result_display = str(node.result)
            if len(result_display) > 70: result_display = result_display[:70] + "..."
            
            print(f"CONSOLE LOG: - Node {node.task_id} (L{node.layer}, Agent: {node.agent_name}, Goal: '{node.goal[:30]}...'): Status={status_str}, Result='{result_display}'")
