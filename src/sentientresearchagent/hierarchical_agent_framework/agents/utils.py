from typing import Any
from loguru import logger
# Import the agent instance
from .definitions.utility_agents import context_summarizer_agno_agent

MAX_SUMMARY_LENGTH_FALLBACK_CHARS = 800 # Character limit fallback
TARGET_WORD_COUNT_FOR_CTX_SUMMARIES = 300 # Default target for LLM summary

def get_context_summary(content: Any, target_word_count: int = TARGET_WORD_COUNT_FOR_CTX_SUMMARIES) -> str:
    if not content:
        return ""

    content_str = ""
    if isinstance(content, str):
        content_str = content
    elif hasattr(content, 'model_dump_json'): # Pydantic model
        content_str = content.model_dump_json(indent=None) # Compact JSON
    else:
        content_str = str(content)

    if not content_str.strip():
        return ""

    # Simple pre-check: if already short enough (based on words) and is plain string.
    # For JSON Pydantic dumps, we might still want to summarize.
    current_word_count = len(content_str.split())
    if isinstance(content, str) and current_word_count < target_word_count:
        # If it's already a string and shorter than the target, return as is.
        # No need to check char length here as it's already short.
        return content_str

    # If summarizer agent failed to initialize, fall back to truncation.
    if context_summarizer_agno_agent is None:
        logger.warning("ContextSummarizer_Agno not available, falling back to truncation for content.")
        return content_str[:MAX_SUMMARY_LENGTH_FALLBACK_CHARS] + ("..." if len(content_str) > MAX_SUMMARY_LENGTH_FALLBACK_CHARS else "")

    logger.debug(f"ContextSummarizer: Requesting summary for content (type: {type(content)}, first 100 chars): '{content_str[:100]}...'")
    try:
        # The AgnoAgent's system prompt already has word count guidance.
        # The input to .run() is the main content to be processed.
        response = context_summarizer_agno_agent.run(content_str)

        summary = response.content if response and response.content else ""

        if not summary.strip():
            logger.warning("ContextSummarizer: Agent returned empty or whitespace summary. Falling back to truncation.")
            return content_str[:MAX_SUMMARY_LENGTH_FALLBACK_CHARS] + ("..." if len(content_str) > MAX_SUMMARY_LENGTH_FALLBACK_CHARS else "")

        # Optional: Post-process to remove common LLM conversational artifacts if any slip through
        summary = summary.strip() # Remove leading/trailing whitespace
        # Example: if LLMs sometimes add "Summary: " or "Here's the summary: "
        common_prefixes_to_remove = ["Summary: ", "Here's the summary: ", "Here is the summary: "]
        for prefix in common_prefixes_to_remove:
            if summary.lower().startswith(prefix.lower()):
                summary = summary[len(prefix):]
                break
        
        summary = summary.strip() # Re-strip after potential prefix removal

        logger.info(f"ContextSummarizer: Generated summary (length {len(summary)}): '{summary[:100]}...'")

        # Enforce hard character limit if LLM summary is too verbose, even after word count instruction.
        if len(summary) > MAX_SUMMARY_LENGTH_FALLBACK_CHARS * 1.2: # Allow some leeway
             logger.warning(f"ContextSummarizer: LLM summary exceeded fallback char limit ({len(summary)} > {MAX_SUMMARY_LENGTH_FALLBACK_CHARS * 1.2}). Truncating.")
             summary = summary[:MAX_SUMMARY_LENGTH_FALLBACK_CHARS] + "..."
        return summary

    except Exception as e:
        logger.error(f"ContextSummarizer: Error during summarization: {e}. Falling back to truncation.")
        return content_str[:MAX_SUMMARY_LENGTH_FALLBACK_CHARS] + ("..." if len(content_str) > MAX_SUMMARY_LENGTH_FALLBACK_CHARS else "")
