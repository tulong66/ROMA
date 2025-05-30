"""
Tests for the new agent configuration system.

This test suite validates the YAML-based configuration system with Python prompts.
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock

from sentientresearchagent.hierarchical_agent_framework.agent_configs.config_loader import (
    AgentConfigLoader, load_agent_configs
)


class TestAgentConfigLoader:
    """Test the AgentConfigLoader class."""
    
    def test_init_with_default_config_dir(self):
        """Test initialization with default config directory."""
        loader = AgentConfigLoader()
        assert loader.config_dir.name == "agent_configs"
        assert loader.agents_config_file.name == "agents.yaml"
    
    def test_init_with_custom_config_dir(self):
        """Test initialization with custom config directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            
            # Create a dummy agents.yaml file
            agents_file = config_dir / "agents.yaml"
            agents_file.write_text("agents: []")
            
            loader = AgentConfigLoader(config_dir)
            assert loader.config_dir == config_dir
            assert loader.agents_config_file == agents_file
    
    def test_init_missing_config_dir(self):
        """Test initialization with missing config directory."""
        with pytest.raises(FileNotFoundError, match="Config directory not found"):
            AgentConfigLoader(Path("/nonexistent/path"))
    
    def test_init_missing_agents_file(self):
        """Test initialization with missing agents.yaml file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            with pytest.raises(FileNotFoundError, match="Agents config file not found"):
                AgentConfigLoader(config_dir)
    
    def test_load_valid_config(self):
        """Test loading a valid configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            agents_file = config_dir / "agents.yaml"
            
            # Create a valid config
            config_data = {
                "agents": [
                    {
                        "name": "TestAgent",
                        "type": "planner",
                        "adapter_class": "PlannerAdapter",
                        "enabled": True,
                        "registration": {
                            "named_keys": ["test_agent"]
                        }
                    }
                ],
                "metadata": {
                    "version": "1.0.0"
                }
            }
            
            with open(agents_file, 'w') as f:
                yaml.dump(config_data, f)
            
            loader = AgentConfigLoader(config_dir)
            config = loader.load_config()
            
            assert "agents" in config
            assert len(config.agents) == 1
            assert config.agents[0].name == "TestAgent"
    
    def test_load_invalid_config_structure(self):
        """Test loading configuration with invalid structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            agents_file = config_dir / "agents.yaml"
            
            # Create invalid config (missing agents section)
            config_data = {"metadata": {"version": "1.0.0"}}
            
            with open(agents_file, 'w') as f:
                yaml.dump(config_data, f)
            
            loader = AgentConfigLoader(config_dir)
            
            with pytest.raises(ValueError, match="Configuration must contain 'agents' section"):
                loader.load_config()
    
    def test_resolve_prompt_valid(self):
        """Test resolving a valid prompt reference."""
        loader = AgentConfigLoader()
        
        # Mock the import and attribute access
        with patch('importlib.import_module') as mock_import:
            mock_module = MagicMock()
            mock_module.TEST_PROMPT = "This is a test prompt"
            mock_import.return_value = mock_module
            
            prompt = loader.resolve_prompt("prompts.test_prompts.TEST_PROMPT")
            assert prompt == "This is a test prompt"
    
    def test_resolve_prompt_invalid_format(self):
        """Test resolving prompt with invalid format."""
        loader = AgentConfigLoader()
        
        with pytest.raises(ValueError, match="Invalid prompt source format"):
            loader.resolve_prompt("invalid_format")
    
    def test_resolve_prompt_missing_module(self):
        """Test resolving prompt from missing module."""
        loader = AgentConfigLoader()
        
        with patch('importlib.import_module', side_effect=ImportError("Module not found")):
            with pytest.raises(ImportError):
                loader.resolve_prompt("prompts.nonexistent.PROMPT")
    
    def test_resolve_prompt_missing_attribute(self):
        """Test resolving missing prompt attribute."""
        loader = AgentConfigLoader()
        
        with patch('importlib.import_module') as mock_import:
            mock_module = MagicMock()
            del mock_module.NONEXISTENT_PROMPT  # Ensure attribute doesn't exist
            mock_import.return_value = mock_module
            
            with pytest.raises(AttributeError):
                loader.resolve_prompt("prompts.test_prompts.NONEXISTENT_PROMPT")
    
    def test_resolve_prompt_non_string(self):
        """Test resolving prompt that's not a string."""
        loader = AgentConfigLoader()
        
        with patch('importlib.import_module') as mock_import:
            mock_module = MagicMock()
            mock_module.NOT_A_STRING = 123  # Not a string
            mock_import.return_value = mock_module
            
            with pytest.raises(TypeError, match="is not a string"):
                loader.resolve_prompt("prompts.test_prompts.NOT_A_STRING")
    
    def test_validate_agent_config_valid(self):
        """Test validating a valid agent configuration."""
        loader = AgentConfigLoader()
        
        from omegaconf import OmegaConf
        agent_config = OmegaConf.create({
            "name": "TestAgent",
            "type": "planner",
            "adapter_class": "PlannerAdapter",
            "registration": {
                "named_keys": ["test_agent"]
            }
        })
        
        errors = loader.validate_agent_config(agent_config)
        assert errors == []
    
    def test_validate_agent_config_missing_required_fields(self):
        """Test validating agent config with missing required fields."""
        loader = AgentConfigLoader()
        
        from omegaconf import OmegaConf
        agent_config = OmegaConf.create({
            "name": "TestAgent"
            # Missing type and adapter_class
        })
        
        errors = loader.validate_agent_config(agent_config)
        assert len(errors) >= 2
        assert any("Missing required field: type" in error for error in errors)
        assert any("Missing required field: adapter_class" in error for error in errors)
    
    def test_validate_agent_config_invalid_type(self):
        """Test validating agent config with invalid type."""
        loader = AgentConfigLoader()
        
        from omegaconf import OmegaConf
        agent_config = OmegaConf.create({
            "name": "TestAgent",
            "type": "invalid_type",
            "adapter_class": "PlannerAdapter",
            "registration": {
                "named_keys": ["test_agent"]
            }
        })
        
        errors = loader.validate_agent_config(agent_config)
        assert any("Invalid agent type: invalid_type" in error for error in errors)
    
    def test_validate_config_duplicate_names(self):
        """Test validating config with duplicate agent names."""
        loader = AgentConfigLoader()
        
        from omegaconf import OmegaConf
        config = OmegaConf.create({
            "agents": [
                {
                    "name": "DuplicateAgent",
                    "type": "planner",
                    "adapter_class": "PlannerAdapter",
                    "registration": {"named_keys": ["agent1"]}
                },
                {
                    "name": "DuplicateAgent",  # Duplicate name
                    "type": "executor",
                    "adapter_class": "ExecutorAdapter",
                    "registration": {"named_keys": ["agent2"]}
                }
            ]
        })
        
        validation = loader.validate_config(config)
        assert not validation["valid"]
        assert any("Duplicate agent name: DuplicateAgent" in error for error in validation["errors"])


class TestAgentConfigIntegration:
    """Integration tests for the agent configuration system."""
    
    def test_load_real_config_file(self):
        """Test loading the actual agents.yaml configuration file."""
        # This test will only pass if the real config file exists and is valid
        try:
            config = load_agent_configs()
            assert "agents" in config
            assert len(config.agents) > 0
            
            # Check that we have some expected agents
            agent_names = [agent.name for agent in config.agents]
            assert "SimpleTestPlanner" in agent_names
            assert "DefaultAggregator" in agent_names
            
        except FileNotFoundError:
            pytest.skip("Real configuration file not found - this is expected during development")
    
    @patch('sentientresearchagent.hierarchical_agent_framework.agent_configs.config_loader.logger')
    def test_load_config_with_warnings(self, mock_logger):
        """Test loading configuration that generates warnings."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            agents_file = config_dir / "agents.yaml"
            
            # Create config with some issues that generate warnings
            config_data = {
                "agents": [
                    {
                        "name": "ValidAgent",
                        "type": "planner",
                        "adapter_class": "PlannerAdapter",
                        "registration": {"named_keys": ["valid_agent"]},
                        "enabled": True
                    },
                    {
                        "name": "DisabledAgent",
                        "type": "executor",
                        "adapter_class": "ExecutorAdapter",
                        "registration": {"named_keys": ["disabled_agent"]},
                        "enabled": False
                    }
                ]
            }
            
            with open(agents_file, 'w') as f:
                yaml.dump(config_data, f)
            
            config = load_agent_configs(config_dir)
            
            # Verify config was loaded
            assert len(config.agents) == 2
            
            # Check that info messages were logged
            mock_logger.info.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 