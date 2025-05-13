from agno.agent import Agent as AgnoAgent
# from agno.models.openai import OpenAIChat # Example if using OpenAI directly via Agno
from agno.models.litellm import LiteLLM  # Using LiteLLM for broader model compatibility
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import PlanOutput, SubTask # Schema for output

# Ensure you have an environment variable for your LLM API key (e.g., OPENAI_API_KEY)
# LiteLLM will pick it up. Or configure LiteLLM globally.

# A simple planner agent for testing.
# Replace 'gpt-3.5-turbo' with your preferred model accessible via LiteLLM.
# For example, if using a local Ollama model: model="ollama/llama2"
# If using OpenRouter: model="openrouter/anthropic/claude-2" (ensure API key is set)

# For testing, let's define a very basic system message.
# A real planner would have a much more detailed system prompt like in your odr_test/agno_agents.py.
PLANNER_SYSTEM_MESSAGE = """You are a task planner.
Given a 'Current Task Goal', break it down into a list of 1 to 3 sub-tasks.
Each sub-task should have a 'goal', a 'task_type' (e.g., 'WRITE', 'SEARCH', 'THINK'),
and a 'node_type' ('EXECUTE' if it's a simple action, 'PLAN' if it needs further breakdown).
You can also suggest an 'agent_name' for each sub-task if applicable.
Respond ONLY with the JSON structure defined by the 'PlanOutput' and 'SubTask' schemas.
"""

# Example: If the input goal is "Write a blog post about AI", you might respond with:
# {
#   "sub_tasks": [
#     {
#       "goal": "Research current trends in AI for blog content",
#       "task_type": "SEARCH",
#       "node_type": "EXECUTE",
#       "agent_name": "BasicSearchAgent"
#     },
#     {
#       "goal": "Draft the blog post outline",
#       "task_type": "THINK",
#       "node_type": "EXECUTE",
#       "agent_name": "OutlineAgent"
#     },
#     {
#       "goal": "Write the full blog post based on research and outline",
#       "task_type": "WRITE",
#       "node_type": "EXECUTE",
#       "agent_name": "WriterAgent"
#     }
#   ]
# }

# Define the AgnoAgent instance for our simple planner
simple_test_planner_agno_agent = AgnoAgent(
    model=LiteLLM(id="openrouter/anthropic/claude-3-7-sonnet"), # Or any other model string LiteLLM supports
    system_message=PLANNER_SYSTEM_MESSAGE,
    response_model=PlanOutput,  # CRUCIAL: This tells Agno to structure the output
    name="SimpleTestPlannerAgent_Agno" # Descriptive name for the Agno agent
    # tools=[] # Add any tools this specific planner might need to consult (unlikely for a simple planner)
)

# You could define more planner agents here, e.g., a research_planner_agent
# research_planner_system_message = "..."
# research_planner_agno_agent = AgnoAgent(...)

print("Defined: simple_test_planner_agno_agent")

# --- Core Research Planner Agent ---
LLM_MODEL_ID_RESEARCH = "openrouter/anthropic/claude-3-7-sonnet"

# Updated System Prompt for CoreResearchPlanner
UPDATED_CORE_RESEARCH_PLANNER_SYSTEM_MESSAGE = """You are a foundational research planner. Given a 'Research Topic', your objective is to create a 2-step execution plan:
1.  A 'SEARCH' task to directly answer the 'Research Topic' using an advanced search capability that provides annotated results. The goal for this task should be the original 'Research Topic'. Assign the agent named 'OpenAICustomSearcher'.
2.  A 'WRITE' task to draft a brief summary based on the output from the 'OpenAICustomSearcher'. The goal should be 'Write a brief summary about the research topic: [Research Topic] using the provided annotated search results'. Assign the agent named 'BasicReportWriter'.

Both sub-tasks must be of 'EXECUTE' node_type.
The 'task_type' for step 1 is 'SEARCH'. For step 2, it's 'WRITE'.
Respond ONLY with the JSON structure defined by 'PlanOutput' and 'SubTask'. Ensure the 'agent_name' field is correctly populated for each sub-task.
"""

core_research_planner_agno_agent = AgnoAgent(
    model=LiteLLM(id=LLM_MODEL_ID_RESEARCH),
    system_message=UPDATED_CORE_RESEARCH_PLANNER_SYSTEM_MESSAGE, # Use the updated prompt
    response_model=PlanOutput,
    name="CoreResearchPlanner_Agno"
)
print("Defined: core_research_planner_agno_agent (Updated for 2-step OpenAICustomSearcher flow)")