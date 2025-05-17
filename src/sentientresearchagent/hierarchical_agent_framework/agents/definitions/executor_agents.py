# In agents/definitions/executor_agents.py
from agno.agent import Agent as AgnoAgent
from agno.models.litellm import LiteLLM
from agno.tools.duckduckgo import DuckDuckGoTools # For SearchExecutor
from agno.models.openai import OpenAIChat

# Import Pydantic models for response structuring
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import WebSearchResultsOutput


# A very basic writer agent for testing.
simple_writer_agno_agent = AgnoAgent(
    model=LiteLLM(id="openrouter/anthropic/claude-3-7-sonnet"), # Replace with your preferred model
    system_message="You are a writer. Write content for the given goal.",
    name="SimpleWriter_Agno"
)

# A very basic search agent placeholder (actual search needs tools)
simple_search_agno_agent = AgnoAgent(
    model=LiteLLM(id="openrouter/anthropic/claude-3-7-sonnet"),
    system_message="You are a searcher. Formulate a query for the given goal.", # This would need a search tool
    name="SimpleSearch_Agno"
)


# --- Research Focused Executor Agents ---
LLM_MODEL_ID_RESEARCH = "openrouter/anthropic/claude-3-7-sonnet" # Specific for these new agents

# --- 1. Search Executor Agent ---
SEARCH_EXECUTOR_SYSTEM_MESSAGE = """You are an efficient search agent. Your sole task is to take the provided 'Search Query Goal' and execute it using the available DuckDuckGo web search tool.
The DuckDuckGo tool will return a list of results, each with 'title', 'href' (link), and 'body' (snippet).
You MUST format your output according to the 'WebSearchResultsOutput' model, where 'results' is a list of dictionaries, each having 'title', 'link', and 'snippet'.
Map 'href' to 'link' and 'body' to 'snippet' in your output.
Your 'query_used' field in the output should be the exact 'Search Query Goal' you were given.
"""

search_executor_agno_agent = AgnoAgent(
    model=OpenAIChat(id="gpt-4.1"),
    system_message=SEARCH_EXECUTOR_SYSTEM_MESSAGE,
    tools=[DuckDuckGoTools()],
    # response_model=WebSearchResultsOutput,
    name="SearchExecutor_Agno"
    # show_tool_calls=True # Useful for debugging tool usage
)


# --- 2. Search Synthesizer Agent ---
SEARCH_SYNTHESIZER_SYSTEM_MESSAGE = """You are a search results synthesizer. You will be given a 'Research Goal' and 'Raw Search Results' (as context, typically from a 'SearchExecutor' agent in WebSearchResultsOutput format).
Your primary task is to carefully review all provided search result snippets and generate a concise, coherent text summary of the information that is most relevant to the original 'Research Goal'.
Extract key facts, figures, and insights. The summary should be in well-formatted markdown.
Output *only* this markdown summary. Do not include any preambles or conversational text.
"""

search_synthesizer_agno_agent = AgnoAgent(
    model=LiteLLM(id=LLM_MODEL_ID_RESEARCH),
    system_message=SEARCH_SYNTHESIZER_SYSTEM_MESSAGE,
    name="SearchSynthesizer_Agno"
    # No response_model here, expects a string (markdown)
)


# --- 3. Basic Report Writer Agent ---
BASIC_REPORT_WRITER_SYSTEM_MESSAGE = """You are an expert academic and research report writer. You will receive a 'Writing Goal' and 'Context'.
The 'Context' will contain synthesized information, potentially from multiple research tasks. This context may include text content and structured citation information (e.g., '[Title](URL)').

Your task is to write a DETAILED and THOROUGH report section that directly fulfills the 'Writing Goal'.
- Use *only* the information provided in the 'Context'. Do not invent facts or information.
- Write in a formal, analytical, and objective tone suitable for a research report.
- Structure your response with clear paragraphs. If the goal implies multiple sub-points, address them comprehensively.
- **Critically, wherever you use information that has an associated citation in the context, you MUST include that citation in your written text.** For example, if the context provides "Solar panels faced an initial 30% tariff ([Source A](URL_A))", your report should integrate this like: "Initial tariffs on solar panels were set at 30% ([Source A](URL_A))." Preserve the markdown link format of the citation.
- Ensure the output is well-formatted markdown.
- Do NOT include any preambles, apologies, or self-references like 'Here is the report section:'.
- Output *only* the written report section.
"""

basic_report_writer_agno_agent = AgnoAgent(
    model=LiteLLM(id=LLM_MODEL_ID_RESEARCH),
    system_message=BASIC_REPORT_WRITER_SYSTEM_MESSAGE,
    name="BasicReportWriter_Agno"
    # No response_model here, expects a string (markdown)
)
