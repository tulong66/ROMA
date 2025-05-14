import re
from typing import List, Optional, Any
from loguru import logger
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import AgentTaskInput, ContextItem, PlannerInput, ExecutionHistoryItem, ExecutionHistoryAndContext, ReplanRequestDetails # Added new models
from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import KnowledgeStore, TaskRecord # Adjusted import
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskStatus # Added import
# Assuming TaskNode related enums/types are not directly needed here, TaskRecord uses Literals

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
        logger.warning(f"ContextBuilder Warning: Max depth reached finding path to root for {task_id}")
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
    logger.info(f"ContextBuilder: Resolving context for task '{current_task_id}' (Agent: {agent_name}, Type: {current_task_type})")
    
    relevant_items: List[ContextItem] = []
    # Keep track of source_task_ids already added to avoid duplicate context items
    processed_context_source_ids = set()

    current_task_record = knowledge_store.get_record(current_task_id)
    if not current_task_record:
        logger.warning(f"ContextBuilder Warning: TaskRecord for current task {current_task_id} not found. Returning empty context.")
        return AgentTaskInput(
            current_task_id=current_task_id, 
            current_goal=current_goal, 
            current_task_type=current_task_type or "UNKNOWN",
            overall_project_goal=overall_project_goal, 
            relevant_context_items=[]
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
        if parent_record and parent_record.output_content is not None:
            # Check if parent is DONE (for general output) or PLAN_DONE (if it's a plan output)
            is_completed_parent = parent_record.status == TaskStatus.DONE.value
            is_plan_done_parent = parent_record.status == TaskStatus.PLAN_DONE.value

            if is_completed_parent or is_plan_done_parent:
                content_desc = parent_record.output_type_description or "parent_output"
                if parent_record.task_type in ['PLAN', 'THINK'] and ("plan" in content_desc or "outline" in content_desc or is_plan_done_parent):
                    content_desc = "parental_plan_or_outline"
                
                relevant_items.append(ContextItem(
                    source_task_id=parent_record.task_id,
                    source_task_goal=parent_record.goal,
                    content=parent_record.output_content,
                    content_type_description=content_desc
                ))
                processed_context_source_ids.add(parent_record.task_id)
                logger.info(f"  Added context from PARENT: {parent_record.task_id} (Status: {parent_record.status})")


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
                    if prereq_record and prereq_record.status == TaskStatus.DONE.value and prereq_record.output_content is not None:
                        relevant_items.append(ContextItem(
                            source_task_id=prereq_record.task_id,
                            source_task_goal=prereq_record.goal,
                            content=prereq_record.output_content,
                            content_type_description=prereq_record.output_type_description or "prerequisite_sibling_output"
                        ))
                        processed_context_source_ids.add(prereq_record.task_id)
                        logger.info(f"  Added context from PREREQUISITE SIBLING: {prereq_record.task_id}")
            except ValueError:
                # Current task not found in its parent's generated children list - might be an issue or an ad-hoc task
                logger.warning(f"ContextBuilder Info: Task {current_task_id} not found in parent {parent_of_current_task_record.task_id}'s generated children list.")


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
            logger.debug(f"  Seeking broad context from children of ancestor '{ancestor_for_broad_context.task_id}'")
            for sibling_branch_id in ancestor_for_broad_context.child_task_ids_generated:
                # Avoid adding context from the current task's own direct parent or self
                if sibling_branch_id == current_task_id or sibling_branch_id == current_task_record.parent_task_id:
                    continue
                if sibling_branch_id in processed_context_source_ids:
                    continue

                sibling_branch_record = knowledge_store.get_record(sibling_branch_id)
                if sibling_branch_record and sibling_branch_record.status == TaskStatus.DONE.value and \
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
                    logger.info(f"  Added BROAD context from ANCESTOR BRANCH: {sibling_branch_record.task_id}")

    # Rule 5: Goal-Aware Context - Fetch explicitly mentioned task IDs in the current goal.
    # E.g., "Summarize results from `root.1.2` and `root.1.3`"
    explicitly_referenced_task_ids = re.findall(r'`(root(?:\.\d+)*)`', current_goal)
    # Could also check current_task_record.input_params_dict if it might contain task IDs

    if explicitly_referenced_task_ids:
        unique_referenced_ids = list(dict.fromkeys(explicitly_referenced_task_ids))
        logger.debug(f"  Task goal references IDs: {unique_referenced_ids}")
        for ref_task_id in unique_referenced_ids:
            if ref_task_id == current_task_id or ref_task_id in processed_context_source_ids:
                continue
            
            referenced_record = knowledge_store.get_record(ref_task_id)
            if referenced_record and referenced_record.status == TaskStatus.DONE.value and referenced_record.output_content is not None: # Check against DONE status
                relevant_items.append(ContextItem(
                    source_task_id=referenced_record.task_id,
                    source_task_goal=referenced_record.goal,
                    content=referenced_record.output_content,
                    content_type_description=referenced_record.output_type_description or "explicit_goal_reference"
                ))
                processed_context_source_ids.add(ref_task_id)
                logger.info(f"  Added context from EXPLICITLY REFERENCED task: {ref_task_id}")
            elif referenced_record:
                 logger.warning(f"    Referenced task {ref_task_id} not {TaskStatus.DONE.value} or no output. Status: {referenced_record.status}")
            else:
                 logger.warning(f"    Referenced task {ref_task_id} not found in KnowledgeStore.")


    # --- Final Logging of Context ---
    if relevant_items:
        logger.success(f"ContextBuilder: Found {len(relevant_items)} relevant context items for task '{current_task_id}':")
        # for item in relevant_items:
        #     content_display = str(item.content)
        #     if len(content_display) > 70: content_display = content_display[:70] + "..."
        #     logger.debug(f"    - Source: {item.source_task_id} ('{item.source_task_goal[:30]}...'), Type: {item.content_type_description}, Content: '{content_display}'")
    else:
        logger.warning(f"ContextBuilder: No relevant context items found for task '{current_task_id}'.")
        
    logger.debug(f"DEBUG: About to create AgentTaskInput. current_task_type variable value: {repr(current_task_type)}")
    return AgentTaskInput(
        current_task_id=current_task_id,
        current_goal=current_goal,
        current_task_type=current_task_type, # Changed 'task_type' to 'current_task_type'
        overall_project_goal=overall_project_goal,
        relevant_context_items=relevant_items
    )

# --- New function to build input specifically for Planner Agents ---
def resolve_input_for_planner_agent(
    current_task_id: str, # The ID of the task that requires planning (or re-planning)
    knowledge_store: KnowledgeStore,
    overall_objective: str, # The ultimate high-level goal
    # Optional parameters that the NodeProcessor will need to supply:
    planning_depth: int = 0, 
    replan_details: Optional[ReplanRequestDetails] = None,
    global_constraints: Optional[List[str]] = None
) -> PlannerInput:
    """
    Constructs the detailed PlannerInput object for a Planner Agent,
    gathering all necessary hierarchical and historical context.
    """
    logger.info(f"ContextBuilder: Resolving INPUT for PLANNER for task '{current_task_id}'")

    current_task_record = knowledge_store.get_record(current_task_id)
    if not current_task_record:
        # This should ideally not happen if NodeProcessor is calling this correctly
        logger.error(f"ContextBuilder Error: TaskRecord for current planning task {current_task_id} not found!")
        # Fallback or raise error - for now, returning a minimal input
        return PlannerInput(
            current_task_goal=f"Error: Task {current_task_id} not found",
            overall_objective=overall_objective
        )

    current_task_goal = current_task_record.goal # The goal of the task needing decomposition

    parent_task_goal: Optional[str] = None
    if current_task_record.parent_task_id:
        parent_record = knowledge_store.get_record(current_task_record.parent_task_id)
        if parent_record:
            parent_task_goal = parent_record.goal

    # --- Populate ExecutionHistoryAndContext ---
    history_and_context = ExecutionHistoryAndContext()
    processed_context_source_ids = set() # To avoid duplicate entries from different rules

    # 1. Prior Sibling Task Outputs
    #    (Leveraging logic similar to Rule 3 of resolve_context_for_agent)
    if current_task_record.parent_task_id:
        parent_of_current_task_record = knowledge_store.get_record(current_task_record.parent_task_id)
        if parent_of_current_task_record and parent_of_current_task_record.child_task_ids_generated:
            try:
                sibling_ids_in_plan = parent_of_current_task_record.child_task_ids_generated
                current_task_index_in_plan = sibling_ids_in_plan.index(current_task_id)
                
                for i in range(current_task_index_in_plan):
                    prereq_sibling_id = sibling_ids_in_plan[i]
                    if prereq_sibling_id in processed_context_source_ids:
                        continue
                    
                    prereq_record = knowledge_store.get_record(prereq_sibling_id)
                    if prereq_record and prereq_record.status == TaskStatus.DONE.value and prereq_record.output_content is not None:
                        # TODO: Implement robust summarization for prereq_record.output_content
                        summary = str(prereq_record.output_content)[:250] + "..." if len(str(prereq_record.output_content)) > 250 else str(prereq_record.output_content)
                        if prereq_record.output_summary: # Prefer pre-computed summary if available
                             summary = prereq_record.output_summary

                        history_and_context.prior_sibling_task_outputs.append(
                            ExecutionHistoryItem(
                                task_goal=prereq_record.goal,
                                outcome_summary=summary, # Placeholder for actual summarization
                                full_output_reference_id=prereq_record.task_id # Assuming task_id can serve as ref
                            )
                        )
                        processed_context_source_ids.add(prereq_record.task_id)
                        logger.info(f"  PLANNER_INPUT: Added SIBLING context: {prereq_record.task_id}")
            except ValueError:
                logger.warning(f"ContextBuilder Info (Planner): Task {current_task_id} not in parent {parent_of_current_task_record.task_id}'s children list.")

    # 2. Relevant Ancestor Outputs
    #    (Leveraging logic from Rule 2 and Rule 4 of resolve_context_for_agent)
    path_to_root = get_task_record_path_to_root(current_task_id, knowledge_store)

    # Direct Parent (if completed and has output)
    if current_task_record.parent_task_id and current_task_record.parent_task_id not in processed_context_source_ids:
        parent_record = knowledge_store.get_record(current_task_record.parent_task_id)
        if parent_record and parent_record.status == TaskStatus.DONE.value and parent_record.output_content is not None:
            summary = str(parent_record.output_content)[:250] + "..." if len(str(parent_record.output_content)) > 250 else str(parent_record.output_content)
            if parent_record.output_summary: summary = parent_record.output_summary
            history_and_context.relevant_ancestor_outputs.append(
                ExecutionHistoryItem(
                    task_goal=parent_record.goal,
                    outcome_summary=summary,
                    full_output_reference_id=parent_record.task_id
                )
            )
            processed_context_source_ids.add(parent_record.task_id)
            logger.info(f"  PLANNER_INPUT: Added PARENT context: {parent_record.task_id}")

    # Broader context from other completed branches of a grandparent (if grandparent was a PLAN node)
    if len(path_to_root) > 2: # Current task has at least a grandparent
        grandparent_record = path_to_root[-3] # Grandparent
        if grandparent_record.node_type == 'PLAN': # Check if grandparent was a planner
            logger.debug(f"  PLANNER_INPUT: Seeking broad context from children of GRANDPARENT '{grandparent_record.task_id}'")
            for uncle_branch_id in grandparent_record.child_task_ids_generated:
                # Avoid current task's own parent branch and already processed items
                if uncle_branch_id == current_task_record.parent_task_id or uncle_branch_id in processed_context_source_ids:
                    continue
                
                uncle_branch_record = knowledge_store.get_record(uncle_branch_id)
                if uncle_branch_record and uncle_branch_record.status == TaskStatus.DONE.value and uncle_branch_record.output_content is not None:
                    summary = str(uncle_branch_record.output_content)[:250] + "..." if len(str(uncle_branch_record.output_content)) > 250 else str(uncle_branch_record.output_content)
                    if uncle_branch_record.output_summary: summary = uncle_branch_record.output_summary
                    history_and_context.relevant_ancestor_outputs.append(
                        ExecutionHistoryItem(
                            task_goal=uncle_branch_record.goal,
                            outcome_summary=summary,
                            full_output_reference_id=uncle_branch_record.task_id
                        )
                    )
                    processed_context_source_ids.add(uncle_branch_id)
                    logger.info(f"  PLANNER_INPUT: Added GRANDPARENT'S SIBLING BRANCH context: {uncle_branch_record.task_id}")
    
    # 3. Global Knowledge Base Summary
    gkb_summary = None
    if hasattr(knowledge_store, 'store_description'):
        # Only access if attribute exists
        store_desc_val = getattr(knowledge_store, 'store_description')
        if store_desc_val: # Check if it's not None or empty
            gkb_summary = store_desc_val
    history_and_context.global_knowledge_base_summary = gkb_summary


    planner_input_data = PlannerInput(
        current_task_goal=current_task_goal,
        overall_objective=overall_objective,
        parent_task_goal=parent_task_goal,
        planning_depth=planning_depth,
        execution_history_and_context=history_and_context,
        replan_request_details=replan_details,
        global_constraints_or_preferences=global_constraints if global_constraints is not None else []
    )

    # logger.debug(f"ContextBuilder: Constructed PlannerInput: {planner_input_data.model_dump_json(indent=2)}")
    return planner_input_data
