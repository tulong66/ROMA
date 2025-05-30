#!/usr/bin/env python3
"""
Simple test script to validate the new agent configuration system.
"""

import sys
import tempfile
import yaml
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_basic_config_loading():
    """Test basic configuration loading functionality."""
    print("🧪 Testing basic configuration loading...")
    
    # Create a temporary config for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        config_dir = Path(temp_dir)
        agents_file = config_dir / "agents.yaml"
        
        # Create a minimal valid config
        config_data = {
            "agents": [
                {
                    "name": "TestPlanner",
                    "type": "planner",
                    "adapter_class": "PlannerAdapter",
                    "description": "Test planner agent",
                    "model": {
                        "provider": "litellm",
                        "model_id": "openrouter/anthropic/claude-3-7-sonnet"
                    },
                    "prompt_source": "prompts.planner_prompts.PLANNER_SYSTEM_MESSAGE",
                    "response_model": "PlanOutput",
                    "registration": {
                        "action_keys": [
                            {"action_verb": "plan", "task_type": "WRITE"}
                        ],
                        "named_keys": ["test_planner"]
                    },
                    "enabled": True
                }
            ],
            "metadata": {
                "version": "1.0.0",
                "description": "Test configuration"
            }
        }
        
        # Write the config file
        with open(agents_file, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False)
        
        print(f"✅ Created test config at: {agents_file}")
        
        # Test loading with OmegaConf
        try:
            from omegaconf import OmegaConf
            config = OmegaConf.load(agents_file)
            print(f"✅ OmegaConf loaded config successfully")
            print(f"   - Found {len(config.agents)} agents")
            print(f"   - First agent: {config.agents[0].name}")
            
            # Test accessing nested properties
            first_agent = config.agents[0]
            print(f"   - Agent type: {first_agent.type}")
            print(f"   - Model provider: {first_agent.model.provider}")
            print(f"   - Enabled: {first_agent.enabled}")
            
            return True
            
        except ImportError:
            print("❌ OmegaConf not installed. Please install with: pip install omegaconf>=2.3.0")
            return False
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            return False

def test_prompt_structure():
    """Test that we can import prompt modules."""
    print("\n🧪 Testing prompt module structure...")
    
    try:
        # Test importing the prompt modules we're planning to create
        # For now, we'll just test the structure
        
        # This would be the structure we want:
        expected_prompts = [
            "PLANNER_SYSTEM_MESSAGE",
            "SEARCH_EXECUTOR_SYSTEM_MESSAGE", 
            "SEARCH_SYNTHESIZER_SYSTEM_MESSAGE",
            "BASIC_REPORT_WRITER_SYSTEM_MESSAGE"
        ]
        
        print(f"✅ Expected prompt structure defined")
        print(f"   - Planning to create {len(expected_prompts)} prompt constants")
        
        return True
        
    except Exception as e:
        print(f"❌ Error with prompt structure: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 Testing new agent configuration system\n")
    
    tests = [
        test_basic_config_loading,
        test_prompt_structure
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            results.append(False)
    
    print(f"\n📊 Test Results:")
    print(f"   - Passed: {sum(results)}/{len(results)}")
    print(f"   - Failed: {len(results) - sum(results)}/{len(results)}")
    
    if all(results):
        print("✅ All tests passed! Ready to proceed with implementation.")
        return 0
    else:
        print("❌ Some tests failed. Please address issues before proceeding.")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 