from agno.agent import Agent as AgnoAgent
from agno.models.litellm import LiteLLM

# Using gpt-4o for consistency, or choose a cheaper/faster model for aggregation
LLM_MODEL_ID_AGGREGATOR = "openrouter/anthropic/claude-3-7-sonnet" # Or your preferred model like "gpt-3.5-turbo"

DEFAULT_AGGREGATOR_SYSTEM_MESSAGE = """You are an expert at summarizing and finalizing results.
You will be provided with a 'Parent Task Goal' and 'Context from Child Tasks'.
The context will contain the results from sub-tasks that were executed to achieve the parent goal.
Your task is to synthesize these results into a single, coherent final answer that directly addresses the 'Parent Task Goal'.
If there's only one significant piece of text in the context (e.g., a final report or summary from a child task), you can present that as the final answer.
Ensure the output is clean and directly usable. For simple summarization tasks where a child task already produced a good summary, just output that summary.
Do not add conversational fluff. Only output the final synthesized answer.
"""

default_aggregator_agno_agent = AgnoAgent(
    model=LiteLLM(id=LLM_MODEL_ID_AGGREGATOR),
    system_message=DEFAULT_AGGREGATOR_SYSTEM_MESSAGE,
    name="DefaultAggregator_Agno"
    # No response_model, expects string output
)
print("Defined: default_aggregator_agno_agent")
