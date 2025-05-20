import asyncio
from typing import Any, Callable, Dict, Optional

from agno.exceptions import StopAgentRun
from agno.tools import tool # For the Agno tool decorator
from rich.console import Console
from rich.prompt import Prompt
from rich.pretty import pprint
from loguru import logger

# Initialize a Rich Console for consistent output
hitl_console = Console()

# Placeholder for the Agno tool and its hook
# We will fill these in next.

async def async_human_confirmation_hook(
    function_name: str, 
    function_call: Callable, 
    arguments: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Asynchronous hook for human confirmation, now with a loop for modifications.
    """
    live = getattr(hitl_console, '_live', None)
    
    # We will pass the current_plan (or data_for_review) in arguments.
    # The hook will return this if modified, or signal approval/abort.
    current_data_for_review = arguments.get('data_for_review')
    checkpoint_name = arguments.get('checkpoint_name', 'Unknown Checkpoint')
    context_msg_template = arguments.get('context_message', 'Please review: {checkpoint_name}')

    while True: # Start of the modification loop
        if live: live.stop()

        # Use a dynamic context message if attempts are made
        attempt_count = arguments.get("_hitl_attempt", 1)
        context_msg = context_msg_template
        if attempt_count > 1:
            context_msg = f"[Attempt {attempt_count}] {context_msg_template}"
        
        hitl_console.rule(f"[bold yellow]Waiting for Human Input: {checkpoint_name}", style="yellow")
        hitl_console.print(f"Context: {context_msg}")
        
        if current_data_for_review: # Show the current plan/data
            hitl_console.print("\n[bold blue]Current Data for Review:[/bold blue]")
            sub_console = Console(width=hitl_console.width - 4)
            with sub_console.capture() as capture:
                sub_console.print(current_data_for_review)
            hitl_console.print(capture.get())

        prompt_message = "Action (Approve[a], Modify[m], Abort[x])"
        choices = ["a", "m", "x"]
        
        logger.info(f"HITL Hook: Prompting user for checkpoint '{checkpoint_name}', attempt {attempt_count}.")

        try:
            user_response_str = await asyncio.to_thread(
                Prompt.ask, prompt_message, choices=choices, default="a", console=hitl_console
            )
        except Exception as e:
            logger.error(f"HITL Hook: Error during Prompt.ask: {e}. Defaulting to 'abort'.")
            user_response_str = "x"

        user_choice = user_response_str.strip().lower()

        output_payload = {
            "user_choice": "unknown",
            "user_message": "",
            "modification_instructions": None,
            "action_result_details": None
        }

        if user_choice == "x": # ABORT
            output_payload["user_choice"] = "aborted"
            output_payload["user_message"] = f"User aborted operation at checkpoint: {checkpoint_name}."
            hitl_console.print(f"[bold red]Operation Aborted by User at '{checkpoint_name}'.[/bold red]")
            if live: live.start()
            raise StopAgentRun(output_payload["user_message"], agent_message=output_payload["user_message"])
        
        elif user_choice == "m": # MODIFY
            hitl_console.print("[cyan]Please provide your modification instructions below:[/cyan]")
            try:
                modification_text = await asyncio.to_thread(
                    Prompt.ask, "Modification Instructions", console=hitl_console
                )
            except Exception as e:
                logger.error(f"HITL Hook: Error during modification prompt: {e}. Aborting modification attempt.")
                modification_text = ""

            if not modification_text.strip():
                 hitl_console.print("[yellow]No modification instructions provided. Re-presenting options.[/yellow]")
                 arguments["_hitl_attempt"] = attempt_count + 1
                 if live: live.start()
                 hitl_console.rule(style="yellow")
                 continue

            output_payload["user_choice"] = "request_modification"
            output_payload["modification_instructions"] = modification_text
            output_payload["user_message"] = f"User requested modification for '{checkpoint_name}': '{modification_text}'"
            logger.info(f"HITL Hook: User requested modification for '{checkpoint_name}': '{modification_text}'")
            if live: live.start()
            hitl_console.rule(style="yellow")
            return output_payload

        else: # APPROVED ('a')
            output_payload["user_choice"] = "approved"
            output_payload["user_message"] = f"User approved operation at checkpoint: {checkpoint_name}."
            hitl_console.print(f"[bold green]Operation Approved by User at '{checkpoint_name}'.[/bold green]")
            
            logger.info(f"HITL Hook: Calling original function '{function_name}' for checkpoint '{checkpoint_name}' after user approval.")
            action_result = await function_call(**arguments)
            output_payload["action_result_details"] = action_result
            
            if live: live.start()
            hitl_console.rule(style="yellow")
            return output_payload


@tool(tool_hooks=[async_human_confirmation_hook])
async def trigger_human_review_tool(
    checkpoint_name: str, 
    context_message: str, 
    data_for_review: Optional[Any] = None
) -> Dict[str, Any]:
    """
    A simple Agno tool that primarily serves to trigger the async_human_confirmation_hook.
    The actual user interaction happens in the hook.

    Args:
        checkpoint_name (str): A name for this review point (e.g., "PostAtomizerCheck", "PlanReview").
        context_message (str): A message to display to the user.
        data_for_review (Optional[Any]): Structured data for the user to review.

    Returns:
        Dict[str, Any]: A dictionary containing the outcome, augmented by the hook.
                         The hook will add 'hitl_user_choice', 'hitl_user_message'.
    """
    logger.info(f"HITL Agno Tool: trigger_human_review_tool executed for checkpoint: {checkpoint_name}.")
    return {
        "tool_name": "trigger_human_review_tool",
        "checkpoint_name": checkpoint_name,
        "status": "Tool execution completed, review handled by hook."
    }


async def request_human_review(
    checkpoint_name: str,
    context_message: str,
    data_for_review: Optional[Any] = None, # This will be the current plan
    node_id: Optional[str] = "N/A",
    current_attempt: int = 1 # Pass current attempt for display
) -> Dict[str, Any]:
    logger.info(f"Node {node_id}: Requesting human review for checkpoint: {checkpoint_name}, Attempt: {current_attempt}")
    
    args_for_hook_and_action = {
        "checkpoint_name": checkpoint_name,
        "context_message": context_message,
        "data_for_review": data_for_review, # Pass current data to the hook
        "_hitl_attempt": current_attempt # For display in the hook
    }

    async def hitl_action_on_approval(**kwargs) -> Dict[str, Any]:
        # This function is called by the hook ONLY IF the user approves.
        # Its result becomes part of the hook's return.
        logger.info(f"HITL Action (Node {node_id}, Checkpoint {kwargs.get('checkpoint_name')}): Approved by user. Action completed.")
        return {
            "action_status": "completed_after_approval",
            "checkpoint_name": kwargs.get('checkpoint_name')
            # No need to include data_for_review here, hook will have it if needed
        }

    try:
        # Call the hook. It now contains the loop.
        # It will return when user Aborts (exception), Approves, or Requests Modification.
        result_from_hook = await async_human_confirmation_hook(
            function_name="hitl_action_on_approval",
            function_call=hitl_action_on_approval,
            arguments=args_for_hook_and_action 
        )
        
        # The hook returns a dict. 'user_choice' will be 'approved' or 'request_modification'.
        # 'aborted' is handled via StopAgentRun.
        user_choice = result_from_hook.get("user_choice") 
        user_message = result_from_hook.get("user_message")
        modification_instructions = result_from_hook.get("modification_instructions")

        logger.info(f"Node {node_id}: Human review for '{checkpoint_name}' completed. User choice: {user_choice}")
        
        # This structure will be returned to NodeProcessor._call_hitl
        final_result = {
            "user_choice": user_choice,
            "message": user_message,
            "modification_instructions": modification_instructions,
            "raw_hook_output": result_from_hook 
        }
        return final_result

    except StopAgentRun as e: # Propagate if hook raises it (user aborted)
        logger.warning(f"Node {node_id}: Human review for '{checkpoint_name}' resulted in StopAgentRun (Aborted by user): {e.agent_message if hasattr(e, 'agent_message') else str(e)}")
        raise e 
    except Exception as e:
        logger.exception(f"Node {node_id}: Unexpected error during HITL process for checkpoint '{checkpoint_name}': {e}")
        raise StopAgentRun(f"Unexpected error during HITL process for {checkpoint_name}: {e}")
