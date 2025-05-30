#!/usr/bin/env python3
"""
Test script for YAML agent integration with existing registry.
"""

import sys
import tempfile
import yaml
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_registry_integration():
    """Test integration of YAML agents with existing registry."""
    print("🧪 Testing Registry Integration...")
    
    try:
        # Import modules
        from sentientresearchagent.hierarchical_agent_framework.agent_configs.registry_integration import RegistryIntegrator
        from sentientresearchagent.hierarchical_agent_framework.agent_configs.config_loader import AgentConfigLoader
        from sentientresearchagent.hierarchical_agent_framework.agents.registry import AGENT_REGISTRY, NAMED_AGENTS
        
        print("✅ Successfully imported integration modules")
        
        # Get initial registry state
        initial_registry_count = len(AGENT_REGISTRY)
        initial_named_count = len(NAMED_AGENTS)
        print(f"📊 Initial registry state: {initial_registry_count} action keys, {initial_named_count} named agents")
        
        # Create test configuration
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            agents_file = config_dir / "agents.yaml"
            
            # Create a simple test config with VALID TaskType values
            config_data = {
                "agents": [
                    {
                        "name": "TestYAMLPlanner",
                        "type": "planner",
                        "adapter_class": "PlannerAdapter",
                        "description": "Test YAML planner",
                        "model": {
                            "provider": "litellm",
                            "model_id": "openrouter/anthropic/claude-3-7-sonnet"
                        },
                        "prompt_source": "prompts.planner_prompts.PLANNER_SYSTEM_MESSAGE",
                        "response_model": "PlanOutput",
                        "registration": {
                            "action_keys": [
                                {"action_verb": "plan", "task_type": "WRITE"}  # Valid TaskType
                            ],
                            "named_keys": ["test_yaml_planner", "yaml_planner"]
                        },
                        "enabled": True
                    },
                    {
                        "name": "TestYAMLCustomSearcher",
                        "type": "custom_search",
                        "adapter_class": "OpenAICustomSearchAdapter",
                        "description": "Test YAML custom searcher",
                        "registration": {
                            "action_keys": [
                                {"action_verb": "execute", "task_type": "SEARCH"}  # Valid TaskType
                            ],
                            "named_keys": ["test_yaml_searcher"]
                        },
                        "enabled": True
                    }
                ],
                "metadata": {"version": "1.0.0"}
            }
            
            # Write config
            with open(agents_file, 'w') as f:
                yaml.dump(config_data, f)
            
            print("✅ Created test YAML configuration")
            
            # Test integration
            config_loader = AgentConfigLoader(config_dir)
            integrator = RegistryIntegrator(config_loader)
            
            # Load and register
            results = integrator.load_and_register_agents()
            
            print(f"✅ Integration completed:")
            print(f"   📋 Action keys registered: {results['registered_action_keys']}")
            print(f"   🏷️  Named keys registered: {results['registered_named_keys']}")
            print(f"   ⏭️  Skipped: {results['skipped_agents']}")
            print(f"   ❌ Failed: {results['failed_registrations']}")
            
            # Verify registry changes
            final_registry_count = len(AGENT_REGISTRY)
            final_named_count = len(NAMED_AGENTS)
            
            registry_increase = final_registry_count - initial_registry_count
            named_increase = final_named_count - initial_named_count
            
            print(f"📊 Registry changes:")
            print(f"   Action keys: {initial_registry_count} → {final_registry_count} (+{registry_increase})")
            print(f"   Named agents: {initial_named_count} → {final_named_count} (+{named_increase})")
            
            # Validate specific registrations with VALID TaskType
            from sentientresearchagent.hierarchical_agent_framework.types import TaskType
            expected_action_key = ("plan", TaskType.WRITE)  # Use TaskType enum
            if expected_action_key in AGENT_REGISTRY:
                print(f"✅ Found expected action key: {expected_action_key}")
            else:
                print(f"❌ Missing expected action key: {expected_action_key}")
                return False
            
            expected_named_key = "test_yaml_planner"
            if expected_named_key in NAMED_AGENTS:
                print(f"✅ Found expected named key: {expected_named_key}")
            else:
                print(f"❌ Missing expected named key: {expected_named_key}")
                return False
            
            # Test validation
            validation = integrator.validate_integration()
            if validation["valid"]:
                print("✅ Integration validation passed")
            else:
                print(f"❌ Integration validation failed: {validation['issues']}")
                return False
            
            # Test status reporting
            status = integrator.get_registry_status()
            print(f"📊 Final status:")
            print(f"   Total registry entries: {status['total_agent_registry_entries']}")
            print(f"   Total named agents: {status['total_named_agents']}")
            print(f"   YAML agents created: {status['yaml_agents_created']}")
            
            return True
            
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_coexistence():
    """Test that legacy and YAML systems can coexist."""
    print("\n🧪 Testing Legacy/YAML Coexistence...")
    
    try:
        from sentientresearchagent.hierarchical_agent_framework.agents.registry import AGENT_REGISTRY, NAMED_AGENTS
        
        # Check that we have agents from both systems
        registry_keys = list(AGENT_REGISTRY.keys())
        named_keys = list(NAMED_AGENTS.keys())
        
        print(f"📊 Current registry state:")
        print(f"   Action keys: {len(registry_keys)}")
        print(f"   Named agents: {len(named_keys)}")
        
        # Look for evidence of both systems
        has_legacy_agents = any("default" in str(key).lower() for key in named_keys)
        has_yaml_agents = any("yaml" in str(key).lower() for key in named_keys)
        
        print(f"🔍 System detection:")
        print(f"   Legacy agents detected: {has_legacy_agents}")
        print(f"   YAML agents detected: {has_yaml_agents}")
        
        if has_legacy_agents and has_yaml_agents:
            print("✅ Both legacy and YAML systems are coexisting")
            return True
        elif has_legacy_agents:
            print("⚠️  Only legacy agents detected (YAML integration may have failed)")
            return False
        elif has_yaml_agents:
            print("⚠️  Only YAML agents detected (legacy system may have failed)")
            return False
        else:
            print("❌ No agents detected from either system")
            return False
            
    except Exception as e:
        print(f"❌ Coexistence test failed: {e}")
        return False

def main():
    """Run integration tests."""
    print("🚀 Testing YAML Agent Integration with Existing Registry\n")
    
    tests = [
        test_registry_integration,
        test_coexistence
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            results.append(False)
    
    print(f"\n📊 Integration Test Results:")
    print(f"   Passed: {sum(results)}/{len(results)}")
    print(f"   Failed: {len(results) - sum(results)}/{len(results)}")
    
    if all(results):
        print("\n✅ All integration tests passed!")
        print("🎉 YAML agent system successfully integrated with legacy registry!")
        return 0
    else:
        print("\n❌ Some integration tests failed.")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 