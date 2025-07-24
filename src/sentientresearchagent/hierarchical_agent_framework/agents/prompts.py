# Basic prompt templates for the adapters.
# The detailed instructions for the agent should be in the agno.Agent's system_message.

INPUT_PROMPT = """Current Task Goal: {input_goal}

Context:
{context_str}"""

AGGREGATOR_PROMPT = """Parent Goal: {input_goal}
Sub-task Results:
{context_str}"""

# You can add more specialized prompt templates here as needed,
# like the COMBINED_SEARCHER_REASONER_SYNTHESIZER_PROMPT from your old prompts.py
# if you plan to use such specific agent patterns. For now, keeping it minimal.

# Example of a more complex prompt if you had a specific agent needing it:
# RESEARCH_SYNTHESIS_PROMPT = """
# Original Research Question: {input_goal}
#
# Provided Information Snippets:
# {context_str} # context_str would be formatted to list research findings
#
# Your Task: Synthesize the provided information snippets into a coherent answer
# for the original research question. Focus on accuracy and conciseness.
# """
