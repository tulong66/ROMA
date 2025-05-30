#!/usr/bin/env python3
"""
Test script for the agent factory.
"""

import sys
import tempfile
import yaml
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_agent_factory():
    """Test the agent factory with a simple configuration."""
    print("🧪 Testing Agent Factory...")
    
    try:
        # Import our modules
        from sentientresearchagent.hierarchical_agent_framework.agent_configs.config_loader import AgentConfigLoader
        from sentientresearchagent.hierarchical_agent_framework.agent_configs.agent_factory import AgentFactory
        from omegaconf import OmegaConf
        
        print("✅ Successfully imported required modules")
        
        # Create a test configuration
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            agents_file = config_dir / "agents.yaml"
            
            # Create a minimal config for testing
            config_data = {
                "agents": [
                    {
                        "name": "TestCustomSearcher",
                        "type": "custom_search",
                        "adapter_class": "OpenAICustomSearchAdapter",
                        "description": "Test custom search agent",
                        "registration": {
                            "action_keys": [
                                {"action_verb": "execute", "task_type": "SEARCH"}
                            ],
                            "named_keys": ["test_searcher"]
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
            
            print(f"✅ Created test config")
            
            # Test loading config
            loader = AgentConfigLoader(config_dir)
            config = loader.load_config()
            
            print(f"✅ Loaded config with {len(config.agents)} agents")
            
            # Test creating factory
            factory = AgentFactory(loader)
            print(f"✅ Created agent factory")
            
            # Test creating a single agent (custom search doesn't need AgnoAgent)
            agent_config = config.agents[0]
            agent_info = factory.create_agent(agent_config)
            
            print(f"✅ Created agent: {agent_info['name']}")
            print(f"   - Type: {agent_info['type']}")
            print(f"   - Adapter: {type(agent_info['adapter']).__name__}")
            print(f"   - Registration keys: {agent_info['registration']['named_keys']}")
            
            return True
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Make sure OmegaConf is installed: pip install omegaconf>=2.3.0")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the test."""
    print("🚀 Testing Agent Factory Implementation\n")
    
    success = test_agent_factory()
    
    if success:
        print("\n✅ Agent factory test passed! Ready to proceed with full implementation.")
        return 0
    else:
        print("\n❌ Agent factory test failed. Please address issues.")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 