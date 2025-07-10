#!/usr/bin/env python3
"""
Simple example showing how tools work with AgnoAgent
"""

from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()

# Configure minimal logging
logger.remove()
logger.add(lambda msg: print(msg), level="INFO", format="{message}")

from agno.agent import Agent
from agno.models.litellm import LiteLLM
from agno.tools.python import PythonTools
from agno.tools.reasoning import ReasoningTools


def main():
    """Simple example of AgnoAgent with tools"""
    
    # 1. Create a model
    model = LiteLLM(
        id="openrouter/google/gemini-2.5-flash",
        temperature=0.2,
        max_tokens=4000
    )
    
    # 2. Define a simple web_search function (mock version for testing)
    def web_search_mock(query: str) -> str:
        """Mock web search for testing - returns fake results"""
        return f"Search results for '{query}': The answer is 42. (This is a mock result)"
    
    # 3. Clean tools function (simplified)
    def clean_tools(tools):
        """Remove problematic attributes from tools"""
        cleaned = []
        for tool in tools:
            # Remove attributes that might cause issues
            if hasattr(tool, 'requires_confirmation'):
                delattr(tool, 'requires_confirmation')
            if hasattr(tool, 'external_execution'):
                delattr(tool, 'external_execution')
            cleaned.append(tool)
        return cleaned
    
    # 4. Create agent with tools
    prompt = """You are a helpful assistant with access to various tools.

Available tools:
- web_search_mock: Search the web for information
- PythonTools: Execute Python code for calculations
- ReasoningTools: Use structured reasoning

When asked a question:
1. Think about which tool would be most helpful
2. Use the appropriate tool
3. Provide a clear answer based on the tool's output

Be concise and direct in your responses."""
    
    # Prepare tools
    tools = [
        web_search_mock,
        PythonTools(base_dir=Path("tmp/python"), run_code=True),
        ReasoningTools()
    ]
    
    # Clean tools
    tools = clean_tools(tools)
    
    # Create agent
    agent = Agent(
        model=model,
        tools=tools,
        system_message=prompt,
        show_tool_calls=True,
        markdown=True,
        reasoning=True  # Enable reasoning
    )
    
    # Test queries
    print("\n" + "="*60)
    print("AgnoAgent with Tools - Simple Example")
    print("="*60 + "\n")
    
    test_queries = [
        "What is 25 * 37? Show your calculation.",
        "Search for information about the Eiffel Tower",
        "Use reasoning to explain why the sky appears blue"
    ]
    
    for query in test_queries:
        print(f"\n📝 Query: {query}")
        print("-" * 40)
        
        try:
            response = agent.run(query)
            print(f"✅ Response:\n{response.content}")
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print("-" * 40)


if __name__ == "__main__":
    main()