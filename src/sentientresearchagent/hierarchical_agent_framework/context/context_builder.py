import re
from typing import List, Optional, Any
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import AgentTaskInput, ContextItem
from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import KnowledgeStore, TaskRecord # Adjusted import
# Assuming TaskNode related enums/types are not directly needed here, TaskRecord uses Literals

# Basic console coloring for logs
def colored(text, color):
    colors = {"green": "\033[92m", "cyan": "\033[96m", "yellow": "\033[93m", "red": "\033[91m", "bold": "\033[1m", "end": "\033[0m"}
    return f"{colors.get(color, '')}{text}{colors['end']}"


def get_task_record_path_to_root(task_id: str, knowledge_store: KnowledgeStore) -> List[TaskRecord]:
    """Helper to get the path of task records from a task_id up to the root."""
    path: List[TaskRecord] = []
    current_id: Optional[str] = task_id
    max_depth = 20 # Safety break for deep hierarchies or loops
    count = 0
    while current_id and count < max_depth:
        record = knowledge_store.get_record(current_id)
        if record:
            path.append(record)
            current_id = record.parent_task_id
        else:
            break
        count +=1
    if count >= max_depth:
        print(colored(f"ContextBuilder Warning: Max depth reached finding path to root for {task_id}", "yellow"))
    return path[::-1] # Return from root to task

def resolve_context_for_agent(
    current_task_id: str,
    current_goal: str,
    current_task_type: str, # String value from TaskNode.task_type.value
    agent_name: str, # Suggested agent name from TaskNode or NodeProcessor
    knowledge_store: KnowledgeStore,
    overall_project_goal: Optional[str] = None,
) -> AgentTaskInput:
    """
    Gathers and structures relevant context for an agent about to process a task.
    The rules for context gathering can be quite sophisticated.
    """
    print(colored(f"ContextBuilder: Resolving context for task '{current_task_id}' (Agent: {agent_name}, Type: {current_task_type})", "cyan"))
    
    relevant_items: List[ContextItem] = []
    # Keep track of source_task_ids already added to avoid duplicate context items
    processed_context_source_ids = set()

    current_task_record = knowledge_store.get_record(current_task_id)
    if not current_task_record:
        print(colored(f"ContextBuilder Warning: TaskRecord for current task {current_task_id} not found. Returning empty context.", "yellow"))
        return AgentTaskInput(
            current_task_id=current_task_id, current_goal=current_goal, task_type=current_task_type,
            overall_project_goal=overall_project_goal, relevant_context_items=[]
        )

    # Rule 1: Aggregators get their direct children's COMPLETED/FAILED output (simplified)
    # Note: NodeProcessor._handle_aggregating_node already prepares child_results directly.
    # This rule here could be a more generic way if context builder was the sole source.
    # For now, we assume NodeProcessor provides the primary context for aggregators.
    # If agent_name (from TaskNode) indicates it's an aggregator, special logic might apply.
    # if "aggregate" in agent_name.lower() or current_task_type == "AGGREGATE":
    #     pass # Covered by NodeProcessor's direct child result passing for now.

    # Rule 2: Writers/Thinkers often benefit from their parent's output if it was a plan/outline.
    if current_task_record.parent_task_id and current_task_record.parent_task_id not in processed_context_source_ids:
        parent_record = knowledge_store.get_record(current_task_record.parent_task_id)
        if parent_record and parent_record.status == 'COMPLETED' and parent_record.output_content is not None:
            # Especially if parent was a PLAN or THINK task that produced an outline/structure
            content_desc = parent_record.output_type_description or "parent_output"
            if parent_record.task_type in ['PLAN', 'THINK'] and ("plan" in content_desc or "outline" in content_desc):
                content_desc = "parental_plan_or_outline"
            
            relevant_items.append(ContextItem(
                source_task_id=parent_record.task_id,
                source_task_goal=parent_record.goal,
                content=parent_record.output_content,
                content_type_description=content_desc
            ))
            processed_context_source_ids.add(parent_record.task_id)
            print(colored(f"  Added context from PARENT: {parent_record.task_id}", "green"))


    # Rule 3: Completed direct prerequisite siblings' output within the same sub-graph.
    # This assumes tasks in a sub-graph might have sequential dependencies.
    if current_task_record.parent_task_id:
        parent_of_current_task_record = knowledge_store.get_record(current_task_record.parent_task_id)
        if parent_of_current_task_record and parent_of_current_task_record.child_task_ids_generated:
            try:
                # These are children *generated by the parent plan*
                sibling_ids_in_plan = parent_of_current_task_record.child_task_ids_generated
                current_task_index_in_plan = sibling_ids_in_plan.index(current_task_id)
                
                for i in range(current_task_index_in_plan):
                    prereq_sibling_id = sibling_ids_in_plan[i]
                    if prereq_sibling_id in processed_context_source_ids:
                        continue
                    
                    prereq_record = knowledge_store.get_record(prereq_sibling_id)
                    if prereq_record and prereq_record.status == 'COMPLETED' and prereq_record.output_content is not None:
                        relevant_items.append(ContextItem(
                            source_task_id=prereq_record.task_id,
                            source_task_goal=prereq_record.goal,
                            content=prereq_record.output_content,
                            content_type_description=prereq_record.output_type_description or "prerequisite_sibling_output"
                        ))
                        processed_context_source_ids.add(prereq_record.task_id)
                        print(colored(f"  Added context from PREREQUISITE SIBLING: {prereq_record.task_id}", "green"))
            except ValueError:
                # Current task not found in its parent's generated children list - might be an issue or an ad-hoc task
                print(colored(f"ContextBuilder Info: Task {current_task_id} not found in parent {parent_of_current_task_record.task_id}'s generated children list.", "yellow"))


    # Rule 4: "Broad Context" for Writers/Thinkers from completed branches of an ancestor plan.
    # This helps provide overall project context or results from parallel high-level tasks.
    # (Simplified version of Rule 5 from your original context_utils.py)
    if current_task_type in ['WRITE', 'THINK']:
        path_to_root = get_task_record_path_to_root(current_task_id, knowledge_store)
        
        # Consider context from siblings of direct parent, or siblings of grandparent.
        # This means looking at children of the grandparent, or children of great-grandparent.
        ancestor_for_broad_context: Optional[TaskRecord] = None
        if len(path_to_root) > 1: # Current task has at least a parent
            ancestor_for_broad_context = path_to_root[-2] # The parent of the current task

        # If parent itself is a plan, its siblings might not be that "broad". Let's try grandparent's children.
        if len(path_to_root) > 2: # Current task has at least a grandparent
             potential_broader_ancestor = path_to_root[-3] # The grandparent of current task
             if potential_broader_ancestor.node_type == 'PLAN': # Grandparent was a plan
                 ancestor_for_broad_context = potential_broader_ancestor
        
        if ancestor_for_broad_context:
            print(colored(f"  Seeking broad context from children of ancestor '{ancestor_for_broad_context.task_id}'", "cyan"))
            for sibling_branch_id in ancestor_for_broad_context.child_task_ids_generated:
                # Avoid adding context from the current task's own direct parent or self
                if sibling_branch_id == current_task_id or sibling_branch_id == current_task_record.parent_task_id:
                    continue
                if sibling_branch_id in processed_context_source_ids:
                    continue

                sibling_branch_record = knowledge_store.get_record(sibling_branch_id)
                if sibling_branch_record and sibling_branch_record.status == 'COMPLETED' and \
                   sibling_branch_record.output_content is not None:
                    
                    content_type_desc = sibling_branch_record.output_type_description or "ancestor_branch_output"
                    # Prioritize aggregated results from other plan branches
                    if sibling_branch_record.node_type == 'PLAN' and "aggregate" in (sibling_branch_record.output_type_description or "").lower():
                        content_type_desc = "aggregated_ancestor_branch_output"
                    
                    relevant_items.append(ContextItem(
                        source_task_id=sibling_branch_record.task_id,
                        source_task_goal=sibling_branch_record.goal,
                        content=sibling_branch_record.output_content,
                        content_type_description=content_type_desc
                    ))
                    processed_context_source_ids.add(sibling_branch_id)
                    print(colored(f"  Added BROAD context from ANCESTOR BRANCH: {sibling_branch_record.task_id}", "green"))

    # Rule 5: Goal-Aware Context - Fetch explicitly mentioned task IDs in the current goal.
    # E.g., "Summarize results from `root.1.2` and `root.1.3`"
    explicitly_referenced_task_ids = re.findall(r'`(root(?:\.\d+)*)`', current_goal)
    # Could also check current_task_record.input_params_dict if it might contain task IDs

    if explicitly_referenced_task_ids:
        unique_referenced_ids = list(dict.fromkeys(explicitly_referenced_task_ids))
        print(colored(f"  Task goal references IDs: {unique_referenced_ids}", "cyan"))
        for ref_task_id in unique_referenced_ids:
            if ref_task_id == current_task_id or ref_task_id in processed_context_source_ids:
                continue
            
            referenced_record = knowledge_store.get_record(ref_task_id)
            if referenced_record and referenced_record.status == 'COMPLETED' and referenced_record.output_content is not None:
                relevant_items.append(ContextItem(
                    source_task_id=referenced_record.task_id,
                    source_task_goal=referenced_record.goal,
                    content=referenced_record.output_content,
                    content_type_description=referenced_record.output_type_description or "explicit_goal_reference"
                ))
                processed_context_source_ids.add(ref_task_id)
                print(colored(f"  Added context from EXPLICITLY REFERENCED task: {ref_task_id}", "green"))
            elif referenced_record:
                 print(colored(f"    Referenced task {ref_task_id} not COMPLETED or no output. Status: {referenced_record.status}", "yellow"))
            else:
                 print(colored(f"    Referenced task {ref_task_id} not found in KnowledgeStore.", "yellow"))


    # --- Final Logging of Context ---
    if relevant_items:
        print(colored(f"ContextBuilder: Found {len(relevant_items)} relevant context items for task '{current_task_id}':", "green"))
        # for item in relevant_items:
        #     content_display = str(item.content)
        #     if len(content_display) > 70: content_display = content_display[:70] + "..."
        #     print(colored(f"    - Source: {item.source_task_id} ('{item.source_task_goal[:30]}...'), Type: {item.content_type_description}, Content: '{content_display}'", "grey"))
    else:
        print(colored(f"ContextBuilder: No relevant context items found for task '{current_task_id}'.", "yellow"))
        

    return AgentTaskInput(
        current_task_id=current_task_id,
        current_goal=current_goal,
        task_type=current_task_type, # Pass the string task_type
        overall_project_goal=overall_project_goal,
        relevant_context_items=relevant_items
    )
