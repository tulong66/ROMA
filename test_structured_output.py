#!/usr/bin/env python3
"""
Test script for structured output functionality in the agent factory.
"""

import sys
import tempfile
import yaml
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_structured_output_agents():
    """Test agents with structured output models."""
    print("🧪 Testing Structured Output Agents...")
    
    try:
        # Import our modules
        from sentientresearchagent.hierarchical_agent_framework.agent_configs.config_loader import AgentConfigLoader
        from sentientresearchagent.hierarchical_agent_framework.agent_configs.agent_factory import AgentFactory
        from omegaconf import OmegaConf
        
        print("✅ Successfully imported required modules")
        
        # Create a test configuration with structured output
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            agents_file = config_dir / "agents.yaml"
            
            # Create config with agents that have structured output
            config_data = {
                "agents": [
                    {
                        "name": "TestAtomizer",
                        "type": "atomizer",
                        "adapter_class": "AtomizerAdapter",
                        "description": "Test atomizer with structured output",
                        "model": {
                            "provider": "litellm",
                            "model_id": "openrouter/anthropic/claude-3-7-sonnet"
                        },
                        "prompt_source": "prompts.atomizer_prompts.ATOMIZER_SYSTEM_MESSAGE",
                        "response_model": "AtomizerOutput",  # Structured output
                        "registration": {
                            "action_keys": [
                                {"action_verb": "atomize", "task_type": None}
                            ],
                            "named_keys": ["test_atomizer"]
                        },
                        "enabled": True
                    },
                    {
                        "name": "TestSearchExecutor",
                        "type": "executor", 
                        "adapter_class": "ExecutorAdapter",
                        "description": "Test search executor with tools and structured output",
                        "model": {
                            "provider": "openai",
                            "model_id": "gpt-4.1"
                        },
                        "prompt_source": "prompts.executor_prompts.SEARCH_EXECUTOR_SYSTEM_MESSAGE",
                        "response_model": "WebSearchResultsOutput",  # Structured output
                        "tools": ["DuckDuckGoTools"],
                        "registration": {
                            "named_keys": ["test_search_executor"]
                        },
                        "enabled": True
                    },
                    {
                        "name": "TestCustomSearcher",
                        "type": "custom_search",
                        "adapter_class": "OpenAICustomSearchAdapter",
                        "description": "Test custom search with adapter params",
                        "adapter_params": {
                            "model_id": "gpt-4.1"
                        },
                        "registration": {
                            "action_keys": [
                                {"action_verb": "execute", "task_type": "SEARCH"}
                            ],
                            "named_keys": ["test_custom_searcher"]
                        },
                        "enabled": True
                    }
                ],
                "metadata": {
                    "version": "1.0.0"
                }
            }
            
            # Write config file
            with open(agents_file, 'w') as f:
                yaml.dump(config_data, f)
            
            print(f"✅ Created test config with structured output agents")
            
            # Test loading config
            loader = AgentConfigLoader(config_dir)
            config = loader.load_config()
            
            print(f"✅ Loaded config with {len(config.agents)} agents")
            
            # Test creating factory
            factory = AgentFactory(loader)
            print(f"✅ Created agent factory")
            
            # Test creating agents with different output types
            agents = {}
            
            for agent_config in config.agents:
                try:
                    agent_info = factory.create_agent(agent_config)
                    agents[agent_config.name] = agent_info
                    
                    print(f"✅ Created agent: {agent_info['name']}")
                    print(f"   - Type: {agent_info['type']}")
                    print(f"   - Adapter: {type(agent_info['adapter']).__name__}")
                    print(f"   - Structured Output: {agent_info['metadata']['has_structured_output']}")
                    if agent_info['metadata']['has_structured_output']:
                        print(f"   - Response Model: {agent_info['metadata']['response_model']}")
                    print(f"   - Has Tools: {agent_info['metadata']['has_tools']}")
                    if agent_info['metadata']['has_tools']:
                        print(f"   - Tools: {agent_info['metadata']['tools']}")
                    print()
                    
                except Exception as e:
                    print(f"❌ Failed to create agent {agent_config.name}: {e}")
                    return False
            
            # Verify we created all expected agents
            expected_agents = ["TestAtomizer", "TestSearchExecutor", "TestCustomSearcher"]
            for expected in expected_agents:
                if expected not in agents:
                    print(f"❌ Missing expected agent: {expected}")
                    return False
            
            # Verify structured output metadata
            atomizer = agents["TestAtomizer"]
            if not atomizer['metadata']['has_structured_output']:
                print(f"❌ TestAtomizer should have structured output")
                return False
            if atomizer['metadata']['response_model'] != "AtomizerOutput":
                print(f"❌ TestAtomizer should have AtomizerOutput response model")
                return False
            
            # Verify tools metadata
            search_executor = agents["TestSearchExecutor"]
            if not search_executor['metadata']['has_tools']:
                print(f"❌ TestSearchExecutor should have tools")
                return False
            if "DuckDuckGoTools" not in search_executor['metadata']['tools']:
                print(f"❌ TestSearchExecutor should have DuckDuckGoTools")
                return False
            
            print(f"✅ All structured output validations passed!")
            return True
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Make sure all dependencies are installed")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the structured output test."""
    print("🚀 Testing Enhanced Agent Factory with Structured Output\n")
    
    success = test_structured_output_agents()
    
    if success:
        print("\n✅ Structured output test passed! The agent factory properly handles:")
        print("   📋 Structured output models (AtomizerOutput, WebSearchResultsOutput, etc.)")
        print("   🔧 Tool integration (DuckDuckGoTools)")
        print("   ⚙️  Adapter parameters")
        print("   📊 Metadata collection")
        return 0
    else:
        print("\n❌ Structured output test failed. Please address issues.")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 