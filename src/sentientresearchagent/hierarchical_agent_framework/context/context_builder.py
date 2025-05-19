import re
from typing import List, Optional, Any
from loguru import logger
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import AgentTaskInput, ContextItem, PlannerInput, ExecutionHistoryItem, ExecutionHistoryAndContext, ReplanRequestDetails # Added new models
from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import KnowledgeStore, TaskRecord # Adjusted import
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskStatus # Added import
# Assuming TaskNode related enums/types are not directly needed here, TaskRecord uses Literals

# NEW IMPORT for the summarization utility
from ..agents.utils import get_context_summary, TARGET_WORD_COUNT_FOR_CTX_SUMMARIES

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
    Context content will be summarized.
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

    # Rule 1: Aggregators - NodeProcessor._handle_aggregating_node prepares child_results directly.
    # This function is generally not called for the AGGREGATE action verb by NodeProcessor,
    # but if it were, specific aggregator context logic would go here or be handled by NodeProcessor.

    # Rule 2: Writers/Thinkers often benefit from their parent's output if it was a plan/outline.
    if current_task_record.parent_task_id and current_task_record.parent_task_id not in processed_context_source_ids:
        parent_record = knowledge_store.get_record(current_task_record.parent_task_id)
        # Check if parent has output_content or output_summary
        if parent_record and (parent_record.output_content is not None or parent_record.output_summary is not None):
            is_completed_parent = parent_record.status == TaskStatus.DONE.value
            is_plan_done_parent = parent_record.status == TaskStatus.PLAN_DONE.value

            if is_completed_parent or is_plan_done_parent:
                content_desc = parent_record.output_type_description or "parent_output"
                if parent_record.task_type in ['PLAN', 'THINK'] and ("plan" in content_desc or "outline" in content_desc or is_plan_done_parent):
                    content_desc = "parental_plan_or_outline"
                
                summarized_content = parent_record.output_summary
                log_reason = f"used existing output_summary (len: {len(summarized_content or '')})"
                if not summarized_content or len(summarized_content.split()) > TARGET_WORD_COUNT_FOR_CTX_SUMMARIES * 1.2:
                    if parent_record.output_content is not None:
                        logger.debug(f"  PARENT ({parent_record.task_id}): Summarizing output_content. Prev summary len: {len(summarized_content or '')}.")
                        summarized_content = get_context_summary(parent_record.output_content, target_word_count=TARGET_WORD_COUNT_FOR_CTX_SUMMARIES)
                        log_reason = f"summarized output_content (original content len: {len(str(parent_record.output_content))}, new summary len: {len(summarized_content)})"
                    elif summarized_content: # Existing summary was too long, and no output_content to re-summarize
                        logger.debug(f"  PARENT ({parent_record.task_id}): Existing output_summary too long, truncating. Len: {len(summarized_content)}.")
                        summarized_content = summarized_content[:(TARGET_WORD_COUNT_FOR_CTX_SUMMARIES * 7)] # Approx char limit
                        log_reason = f"truncated long existing output_summary (new len: {len(summarized_content)})"
                
                if summarized_content and summarized_content.strip():
                    relevant_items.append(ContextItem(
                        source_task_id=parent_record.task_id,
                        source_task_goal=parent_record.goal,
                        content=summarized_content,
                        content_type_description=content_desc
                    ))
                    processed_context_source_ids.add(parent_record.task_id)
                    logger.info(f"  Added context from PARENT: {parent_record.task_id} (Status: {parent_record.status}). How: {log_reason}. Final len: {len(summarized_content)}")
                else:
                    logger.warning(f"  PARENT ({parent_record.task_id}): Summarization resulted in empty content. Not added.")


    # Rule 3: Completed direct prerequisite siblings' output within the same sub-graph.
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
                    if prereq_record and prereq_record.status == TaskStatus.DONE.value and \
                       (prereq_record.output_content is not None or prereq_record.output_summary is not None):
                        
                        summarized_content = prereq_record.output_summary
                        log_reason = f"used existing output_summary (len: {len(summarized_content or '')})"
                        if not summarized_content or len(summarized_content.split()) > TARGET_WORD_COUNT_FOR_CTX_SUMMARIES * 1.2:
                            if prereq_record.output_content is not None:
                                logger.debug(f"  PREREQ SIBLING ({prereq_record.task_id}): Summarizing output_content. Prev summary len: {len(summarized_content or '')}.")
                                summarized_content = get_context_summary(prereq_record.output_content, target_word_count=TARGET_WORD_COUNT_FOR_CTX_SUMMARIES)
                                log_reason = f"summarized output_content (original content len: {len(str(prereq_record.output_content))}, new summary len: {len(summarized_content)})"
                            elif summarized_content: # Existing summary was too long
                                logger.debug(f"  PREREQ SIBLING ({prereq_record.task_id}): Existing output_summary too long, truncating. Len: {len(summarized_content)}.")
                                summarized_content = summarized_content[:(TARGET_WORD_COUNT_FOR_CTX_SUMMARIES * 7)]
                                log_reason = f"truncated long existing output_summary (new len: {len(summarized_content)})"

                        if summarized_content and summarized_content.strip():
                            relevant_items.append(ContextItem(
                                source_task_id=prereq_record.task_id,
                                source_task_goal=prereq_record.goal,
                                content=summarized_content,
                                content_type_description=prereq_record.output_type_description or "prerequisite_sibling_output"
                            ))
                            processed_context_source_ids.add(prereq_record.task_id)
                            logger.info(f"  Added context from PREREQUISITE SIBLING: {prereq_record.task_id}. How: {log_reason}. Final len: {len(summarized_content)}")
                        else:
                            logger.warning(f"  PREREQ SIBLING ({prereq_record.task_id}): Summarization resulted in empty content. Not added.")
            except ValueError:
                logger.warning(f"ContextBuilder Info: Task {current_task_id} not found in parent {parent_of_current_task_record.task_id}'s generated children list.")


    # Rule 4: "Broad Context" for Writers/Thinkers from completed branches of an ancestor plan.
    if current_task_type in ['WRITE', 'THINK']:
        path_to_root = get_task_record_path_to_root(current_task_id, knowledge_store)
        ancestor_for_broad_context: Optional[TaskRecord] = None
        if len(path_to_root) > 1: 
            ancestor_for_broad_context = path_to_root[-2] 
        if len(path_to_root) > 2: 
             potential_broader_ancestor = path_to_root[-3] 
             if potential_broader_ancestor.node_type == 'PLAN': 
                 ancestor_for_broad_context = potential_broader_ancestor
        
        if ancestor_for_broad_context:
            logger.debug(f"  Seeking broad context from children of ancestor '{ancestor_for_broad_context.task_id}'")
            for sibling_branch_id in ancestor_for_broad_context.child_task_ids_generated:
                if sibling_branch_id == current_task_id or sibling_branch_id == current_task_record.parent_task_id:
                    continue
                if sibling_branch_id in processed_context_source_ids:
                    continue

                sibling_branch_record = knowledge_store.get_record(sibling_branch_id)
                if sibling_branch_record and sibling_branch_record.status == TaskStatus.DONE.value and \
                   (sibling_branch_record.output_content is not None or sibling_branch_record.output_summary is not None):
                    
                    content_type_desc = sibling_branch_record.output_type_description or "ancestor_branch_output"
                    if sibling_branch_record.node_type == 'PLAN' and "aggregate" in (sibling_branch_record.output_type_description or "").lower():
                        content_type_desc = "aggregated_ancestor_branch_output"

                    summarized_content = sibling_branch_record.output_summary
                    log_reason = f"used existing output_summary (len: {len(summarized_content or '')})"
                    if not summarized_content or len(summarized_content.split()) > TARGET_WORD_COUNT_FOR_CTX_SUMMARIES * 1.2:
                        if sibling_branch_record.output_content is not None:
                            logger.debug(f"  ANCESTOR BRANCH ({sibling_branch_record.task_id}): Summarizing output_content. Prev summary len: {len(summarized_content or '')}.")
                            summarized_content = get_context_summary(sibling_branch_record.output_content, target_word_count=TARGET_WORD_COUNT_FOR_CTX_SUMMARIES)
                            log_reason = f"summarized output_content (original content len: {len(str(sibling_branch_record.output_content))}, new summary len: {len(summarized_content)})"
                        elif summarized_content: # Existing summary was too long
                            logger.debug(f"  ANCESTOR BRANCH ({sibling_branch_record.task_id}): Existing output_summary too long, truncating. Len: {len(summarized_content)}.")
                            summarized_content = summarized_content[:(TARGET_WORD_COUNT_FOR_CTX_SUMMARIES * 7)]
                            log_reason = f"truncated long existing output_summary (new len: {len(summarized_content)})"
                    
                    if summarized_content and summarized_content.strip():
                        relevant_items.append(ContextItem(
                            source_task_id=sibling_branch_record.task_id,
                            source_task_goal=sibling_branch_record.goal,
                            content=summarized_content,
                            content_type_description=content_type_desc
                        ))
                        processed_context_source_ids.add(sibling_branch_id)
                        logger.info(f"  Added BROAD context from ANCESTOR BRANCH: {sibling_branch_record.task_id}. How: {log_reason}. Final len: {len(summarized_content)}")
                    else:
                        logger.warning(f"  ANCESTOR BRANCH ({sibling_branch_record.task_id}): Summarization resulted in empty content. Not added.")

    # Rule 5: Goal-Aware Context - Fetch explicitly mentioned task IDs in the current goal.
    explicitly_referenced_task_ids = re.findall(r'`(root(?:\.\d+)*)`', current_goal)

    if explicitly_referenced_task_ids:
        unique_referenced_ids = list(dict.fromkeys(explicitly_referenced_task_ids))
        logger.debug(f"  Task goal references IDs: {unique_referenced_ids}")
        for ref_task_id in unique_referenced_ids:
            if ref_task_id == current_task_id or ref_task_id in processed_context_source_ids:
                continue
            
            referenced_record = knowledge_store.get_record(ref_task_id)
            if referenced_record and referenced_record.status == TaskStatus.DONE.value and \
               (referenced_record.output_content is not None or referenced_record.output_summary is not None):
                
                summarized_content = referenced_record.output_summary
                log_reason = f"used existing output_summary (len: {len(summarized_content or '')})"
                if not summarized_content or len(summarized_content.split()) > TARGET_WORD_COUNT_FOR_CTX_SUMMARIES * 1.2:
                    if referenced_record.output_content is not None:
                        logger.debug(f"  EXPLICIT REF ({referenced_record.task_id}): Summarizing output_content. Prev summary len: {len(summarized_content or '')}.")
                        summarized_content = get_context_summary(referenced_record.output_content, target_word_count=TARGET_WORD_COUNT_FOR_CTX_SUMMARIES)
                        log_reason = f"summarized output_content (original content len: {len(str(referenced_record.output_content))}, new summary len: {len(summarized_content)})"
                    elif summarized_content: # Existing summary was too long
                        logger.debug(f"  EXPLICIT REF ({referenced_record.task_id}): Existing output_summary too long, truncating. Len: {len(summarized_content)}.")
                        summarized_content = summarized_content[:(TARGET_WORD_COUNT_FOR_CTX_SUMMARIES * 7)]
                        log_reason = f"truncated long existing output_summary (new len: {len(summarized_content)})"

                if summarized_content and summarized_content.strip():
                    relevant_items.append(ContextItem(
                        source_task_id=referenced_record.task_id,
                        source_task_goal=referenced_record.goal,
                        content=summarized_content,
                        content_type_description=referenced_record.output_type_description or "explicit_goal_reference"
                    ))
                    processed_context_source_ids.add(ref_task_id)
                    logger.info(f"  Added context from EXPLICITLY REFERENCED task: {ref_task_id}. How: {log_reason}. Final len: {len(summarized_content)}")
                else:
                    logger.warning(f"  EXPLICIT REF ({referenced_record.task_id}): Summarization resulted in empty content. Not added.")
            elif referenced_record:
                 logger.warning(f"    Referenced task {ref_task_id} not {TaskStatus.DONE.value} or no output/summary. Status: {referenced_record.status}")
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
    global_constraints: Optional[List[str]] = None,
    # NEW: For re-planning, pass outputs from successful children of the previous failed plan
    previous_attempt_successful_outputs: Optional[List[ExecutionHistoryItem]] = None
) -> PlannerInput:
    """
    Gathers and structures relevant context for a PLANNER agent.
    This is more specialized than the generic resolve_context_for_agent.
    """
    logger.info(f"ContextBuilder: Resolving INPUT for PLANNER for task '{current_task_id}'")

    current_task_record = knowledge_store.get_record(current_task_id)
    if not current_task_record:
        # This should ideally not happen if NodeProcessor calls this correctly
        logger.error(f"ContextBuilder CRITICAL: TaskRecord for current planning task {current_task_id} not found.")
        # Return a minimal PlannerInput to avoid crashing, but this is an error state
        return PlannerInput(
            current_task_goal="Error: Original task goal not found",
            overall_objective=overall_objective,
            parent_task_goal=None,
            planning_depth=planning_depth,
            execution_history_and_context=ExecutionHistoryAndContext(), # Empty context
            replan_request_details=replan_details,
            global_constraints_or_preferences=global_constraints or []
        )

    current_task_goal = current_task_record.goal
    parent_task_goal: Optional[str] = None
    relevant_ancestor_outputs: List[ExecutionHistoryItem] = []
    prior_sibling_task_outputs_for_context: List[ExecutionHistoryItem] = []


    # 1. Get Parent Task Goal and Relevant Ancestor Outputs
    path_to_root = get_task_record_path_to_root(current_task_id, knowledge_store)
    if len(path_to_root) > 1:
        parent_task_record = path_to_root[-2] # The one before current_task_id in the path
        parent_task_goal = parent_task_record.goal
        
        # For ancestor outputs, we can take the parent's output summary if available and DONE/PLAN_DONE
        if parent_task_record.status in [TaskStatus.DONE.value, TaskStatus.PLAN_DONE.value]:
            parent_summary = parent_task_record.output_summary
            log_reason = "used existing output_summary"
            if not parent_summary or len(parent_summary.split()) > TARGET_WORD_COUNT_FOR_CTX_SUMMARIES * 1.2:
                if parent_task_record.output_content is not None:
                    parent_summary = get_context_summary(parent_task_record.output_content, target_word_count=TARGET_WORD_COUNT_FOR_CTX_SUMMARIES)
                    log_reason = f"summarized output_content (original content len: {len(str(parent_task_record.output_content))}, summary len: {len(parent_summary)})"
                elif parent_summary: # Existing summary too long
                     parent_summary = parent_summary[:(TARGET_WORD_COUNT_FOR_CTX_SUMMARIES * 7)]
                     log_reason = f"truncated long existing output_summary (summary len: {len(parent_summary)})"

            if parent_summary and parent_summary.strip():
                relevant_ancestor_outputs.append(ExecutionHistoryItem(
                    task_goal=parent_task_record.goal,
                    outcome_summary=parent_summary,
                    full_output_reference_id=parent_task_record.task_id
                ))
                logger.info(f"  PLANNER_INPUT: Added PARENT context from: {parent_task_record.task_id} (Status: {parent_task_record.status}). How: {log_reason}")
            else:
                logger.warning(f"  PLANNER_INPUT (Parent {parent_task_record.task_id}): Summarization resulted in empty content. Not added to relevant_ancestor_outputs.")


    # 2. Get Prior Sibling Task Outputs
    # If it's a re-plan and specific successful outputs from the previous attempt are provided, use them.
    if replan_details and previous_attempt_successful_outputs is not None:
        prior_sibling_task_outputs_for_context = previous_attempt_successful_outputs
        logger.info(f"  PLANNER_INPUT (Re-plan): Using {len(previous_attempt_successful_outputs)} successful outputs from previous attempt as prior_sibling_task_outputs.")
    elif current_task_record.parent_task_id: # Normal planning, not a re-plan with explicit previous outputs
        parent_of_current_task_record = knowledge_store.get_record(current_task_record.parent_task_id)
        if parent_of_current_task_record and parent_of_current_task_record.child_task_ids_generated:
            try:
                sibling_ids_in_plan = parent_of_current_task_record.child_task_ids_generated
                current_task_index_in_plan = sibling_ids_in_plan.index(current_task_id)
                
                for i in range(current_task_index_in_plan):
                    prereq_sibling_id = sibling_ids_in_plan[i]
                    prereq_record = knowledge_store.get_record(prereq_sibling_id)
                    if prereq_record and prereq_record.status == TaskStatus.DONE.value:
                        summary = prereq_record.output_summary
                        log_reason_sib = "used existing output_summary"
                        if not summary or len(summary.split()) > TARGET_WORD_COUNT_FOR_CTX_SUMMARIES * 1.2:
                            if prereq_record.output_content is not None:
                                summary = get_context_summary(prereq_record.output_content, target_word_count=TARGET_WORD_COUNT_FOR_CTX_SUMMARIES)
                                log_reason_sib = f"summarized output_content (original content len: {len(str(prereq_record.output_content))}, summary len: {len(summary)})"
                            elif summary: # Existing summary too long
                                summary = summary[:(TARGET_WORD_COUNT_FOR_CTX_SUMMARIES * 7)]
                                log_reason_sib = f"truncated long existing output_summary (summary len: {len(summary)})"
                        
                        if summary and summary.strip():
                            prior_sibling_task_outputs_for_context.append(ExecutionHistoryItem(
                                task_goal=prereq_record.goal,
                                outcome_summary=summary,
                                full_output_reference_id=prereq_record.task_id
                            ))
                            logger.info(f"  PLANNER_INPUT: Added SIBLING context from: {prereq_record.task_id}. How: {log_reason_sib}")
                        else:
                            logger.warning(f"  PLANNER_INPUT (Sibling {prereq_record.task_id}): Summarization resulted in empty content. Not added to prior_sibling_task_outputs_for_context.")
            except ValueError:
                 pass # Task not in parent's list, or other issue, means no prior siblings by this logic.

    # 3. Global Knowledge Base Summary (Simplified for now)
    # This could be a summary of all DONE root-level tasks or other heuristics
    global_knowledge_summary: Optional[str] = None # Placeholder

    exec_history_context = ExecutionHistoryAndContext(
        prior_sibling_task_outputs=prior_sibling_task_outputs_for_context,
        relevant_ancestor_outputs=relevant_ancestor_outputs,
        global_knowledge_base_summary=global_knowledge_summary
    )

    planner_input = PlannerInput(
        current_task_goal=current_task_goal,
        overall_objective=overall_objective,
        parent_task_goal=parent_task_goal,
        planning_depth=planning_depth,
        execution_history_and_context=exec_history_context,
        replan_request_details=replan_details,
        global_constraints_or_preferences=global_constraints or []
    )
    
    logger.success(f"ContextBuilder: Successfully resolved PlannerInput for task '{current_task_id}'. "
                   f"Replan: {'Yes' if replan_details else 'No'}. "
                   f"Prior Siblings in context: {len(prior_sibling_task_outputs_for_context)}. "
                   f"Ancestor Context Items: {len(relevant_ancestor_outputs)}.")

    return planner_input
