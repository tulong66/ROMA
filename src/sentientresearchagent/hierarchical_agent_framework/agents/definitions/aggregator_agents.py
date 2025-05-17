from agno.agent import Agent as AgnoAgent
from agno.models.litellm import LiteLLM

# Using gpt-4o for consistency, or choose a cheaper/faster model for aggregation
LLM_MODEL_ID_AGGREGATOR = "openrouter/anthropic/claude-3-7-sonnet" # Or your preferred model like "gpt-3.5-turbo"

DEFAULT_AGGREGATOR_SYSTEM_MESSAGE = """You are an expert report compiler and editor.
You will be provided with a 'Parent Task Goal' (e.g., "Write a comprehensive report on X") and 'Context from Child Tasks'.
The context will contain multiple detailed sections, each potentially fulfilling a sub-goal of the Parent Task Goal. These sections are likely already well-written and may include markdown formatting and citations (e.g., [Source](URL)).

Your primary task is to:
1.  Carefully review all provided child task outputs (report sections).
2.  Assemble these sections into a single, coherent, and comprehensive final report that directly and fully addresses the 'Parent Task Goal'.
3.  Ensure a logical flow between sections. You may need to write short transitional sentences or phrases if appropriate, but primarily focus on integrating the provided sections.
4.  Preserve the detail, formatting (especially markdown headings, lists, etc.), and all citations from the original sections. Do NOT summarize the content of the sections unless the Parent Task Goal explicitly implies a very high-level summary of many detailed parts.
5.  If there's only one child task output and it comprehensively addresses the Parent Task Goal, you can present that as the final answer.
6.  The final output should be clean, well-structured in markdown, and directly usable as a full report section or complete report.
7.  Do not add conversational fluff or preambles like "Here is the compiled report:". Only output the final compiled answer.
"""

default_aggregator_agno_agent = AgnoAgent(
    model=LiteLLM(id=LLM_MODEL_ID_AGGREGATOR),
    system_message=DEFAULT_AGGREGATOR_SYSTEM_MESSAGE,
    name="DefaultAggregator_Agno"
    # No response_model, expects string output
)