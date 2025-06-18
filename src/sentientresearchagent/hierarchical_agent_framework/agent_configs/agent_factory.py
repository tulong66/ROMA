"""
Agent Factory

Creates agent instances from YAML configuration and Python prompts.
Enhanced to handle structured outputs like the original definitions.
"""

import importlib
import os
from typing import Dict, Any, Optional, List, Union, Type
from loguru import logger

try:
    from omegaconf import DictConfig
except ImportError:
    logger.error("OmegaConf not installed. Please install with: pip install omegaconf>=2.3.0")
    raise

try:
    from agno.agent import Agent as AgnoAgent
    from agno.models.litellm import LiteLLM
    from agno.models.openai import OpenAIChat
    from agno.tools.duckduckgo import DuckDuckGoTools
except ImportError as e:
    logger.error(f"Agno dependencies not available: {e}")
    raise

from ..agents.adapters import (
    PlannerAdapter, ExecutorAdapter, AtomizerAdapter, 
    AggregatorAdapter, PlanModifierAdapter
)
from ..agents.definitions.custom_searchers import OpenAICustomSearchAdapter, GeminiCustomSearchAdapter
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import (
    PlanOutput, AtomizerOutput, WebSearchResultsOutput, 
    CustomSearcherOutput, PlanModifierInput
)
from ..types import TaskType
from sentientresearchagent.hierarchical_agent_framework.agents.base_adapter import BaseAdapter
from sentientresearchagent.hierarchical_agent_framework.agents.registry import AgentRegistry
from sentientresearchagent.hierarchical_agent_framework.agent_blueprints import AgentBlueprint

try:
    from dotenv import load_dotenv
    # Load .env file at module level to ensure environment variables are available
    load_dotenv()
    logger.debug("Loaded environment variables from .env file")
except ImportError:
    logger.warning("python-dotenv not installed. Environment variables from .env files will not be loaded automatically.")

def _validate_provider_environment(provider: str, model_id: str) -> None:
    """
    Validate that required environment variables are set for specific LLM providers.
    
    Args:
        provider: The LLM provider (litellm, openai, etc.)
        model_id: The model identifier
        
    Raises:
        ValueError: If required environment variables are missing
    """
    if provider == "litellm":
        # Determine the actual provider from the model_id
        if model_id.startswith("openrouter/"):
            # OpenRouter models require OPENROUTER_API_KEY
            env_var = "OPENROUTER_API_KEY"
            if not os.getenv(env_var):
                raise ValueError(
                    f"OpenRouter model '{model_id}' requires {env_var} environment variable to be set. "
                    f"Please add {env_var}=your_openrouter_api_key to your .env file."
                )
            logger.debug(f"✅ Found {env_var} for OpenRouter model {model_id}")
                
        elif model_id.startswith("anthropic/"):
            # Anthropic models require ANTHROPIC_API_KEY
            env_var = "ANTHROPIC_API_KEY"
            if not os.getenv(env_var):
                raise ValueError(
                    f"Anthropic model '{model_id}' requires {env_var} environment variable to be set. "
                    f"Please add {env_var}=your_anthropic_api_key to your .env file."
                )
            logger.debug(f"✅ Found {env_var} for Anthropic model {model_id}")
                
        elif model_id.startswith("openai/") or model_id.startswith("gpt-"):
            # OpenAI models require OPENAI_API_KEY
            env_var = "OPENAI_API_KEY"
            if not os.getenv(env_var):
                raise ValueError(
                    f"OpenAI model '{model_id}' requires {env_var} environment variable to be set. "
                    f"Please add {env_var}=your_openai_api_key to your .env file."
                )
            logger.debug(f"✅ Found {env_var} for OpenAI model {model_id}")
                
        elif model_id.startswith("azure/"):
            # Azure models require AZURE_API_KEY
            env_var = "AZURE_API_KEY"
            if not os.getenv(env_var):
                raise ValueError(
                    f"Azure model '{model_id}' requires {env_var} environment variable to be set. "
                    f"Please add {env_var}=your_azure_api_key to your .env file."
                )
            logger.debug(f"✅ Found {env_var} for Azure model {model_id}")
                
        elif model_id.startswith("fireworks_ai/") or model_id.startswith("fireworks/"):
            # Fireworks AI models require FIREWORKS_AI_API_KEY
            env_var = "FIREWORKS_AI_API_KEY"
            if not os.getenv(env_var):
                raise ValueError(
                    f"Fireworks AI model '{model_id}' requires {env_var} environment variable to be set. "
                    f"Please add {env_var}=your_fireworks_ai_api_key to your .env file."
                )
            logger.debug(f"✅ Found {env_var} for Fireworks AI model {model_id}")
                
        else:
            # For other providers, warn but don't fail
            logger.warning(
                f"Unknown LiteLLM model provider for '{model_id}'. "
                f"Please ensure appropriate environment variables are set. "
                f"Common providers: openrouter/, anthropic/, openai/, azure/, fireworks_ai/"
            )
            
    elif provider == "openai":
        # Direct OpenAI provider
        env_var = "OPENAI_API_KEY"
        if not os.getenv(env_var):
            raise ValueError(
                f"OpenAI provider requires {env_var} environment variable to be set. "
                f"Please add {env_var}=your_openai_api_key to your .env file."
            )
        logger.debug(f"✅ Found {env_var} for OpenAI provider")
        
    elif provider == "fireworks" or provider == "fireworks_ai":
        # Direct Fireworks AI provider
        env_var = "FIREWORKS_AI_API_KEY"
        if not os.getenv(env_var):
            raise ValueError(
                f"Fireworks AI provider requires {env_var} environment variable to be set. "
                f"Please add {env_var}=your_fireworks_ai_api_key to your .env file."
            )
        logger.debug(f"✅ Found {env_var} for Fireworks AI provider")

    elif provider == "google" or provider == "gemini":
        # Google/Gemini provider
        env_var = "GOOGLE_API_KEY"
        alt_env_var = "GEMINI_API_KEY"
        if not (os.getenv(env_var) or os.getenv(alt_env_var)):
            raise ValueError(
                f"Google/Gemini provider requires {env_var} or {alt_env_var} environment variable to be set. "
                f"Please add one of these to your .env file."
            )
        logger.debug(f"✅ Found API key for Google/Gemini provider")


class AgentFactory:
    """Factory for creating agent instances from configuration with structured output support."""
    
    def __init__(self, config_loader):
        """
        Initialize the agent factory.
        
        Args:
            config_loader: AgentConfigLoader instance for resolving prompts
        """
        self.config_loader = config_loader
        self._adapter_classes = {
            "PlannerAdapter": PlannerAdapter,
            "ExecutorAdapter": ExecutorAdapter,
            "AtomizerAdapter": AtomizerAdapter,
            "AggregatorAdapter": AggregatorAdapter,
            "PlanModifierAdapter": PlanModifierAdapter,
            "OpenAICustomSearchAdapter": OpenAICustomSearchAdapter,
            "GeminiCustomSearchAdapter": GeminiCustomSearchAdapter,
        }
        
        # Enhanced response models mapping
        self._response_models = {
            "PlanOutput": PlanOutput,
            "AtomizerOutput": AtomizerOutput,
            "WebSearchResultsOutput": WebSearchResultsOutput,
            "CustomSearcherOutput": CustomSearcherOutput,
            # Add more as needed
        }
        
        # Enhanced tools mapping
        self._tools = {
            "DuckDuckGoTools": DuckDuckGoTools,
            # Add more tools as they become available
        }
        
        # Model providers mapping
        self._model_providers = {
            "litellm": LiteLLM,
            "openai": OpenAIChat,
        }
    
    def resolve_response_model(self, response_model_name: str) -> Optional[Type]:
        """
        Resolve a response model name to the actual Pydantic model class.
        
        Args:
            response_model_name: Name of the response model
            
        Returns:
            Pydantic model class or None
        """
        if response_model_name in self._response_models:
            return self._response_models[response_model_name]
        
        # Try to import dynamically if not in our mapping
        try:
            # Try importing from agent_io_models
            module = importlib.import_module(
                "sentientresearchagent.hierarchical_agent_framework.context.agent_io_models"
            )
            if hasattr(module, response_model_name):
                model_class = getattr(module, response_model_name)
                self._response_models[response_model_name] = model_class
                return model_class
        except ImportError:
            pass
        
        logger.warning(f"Unknown response model: {response_model_name}")
        return None
    
    def create_model_instance(self, model_config: DictConfig) -> Union[LiteLLM, OpenAIChat]:
        """
        Create a model instance from configuration with proper environment validation.
        
        Args:
            model_config: Model configuration from YAML
            
        Returns:
            Model instance
            
        Raises:
            ValueError: If provider is unsupported or required API keys are missing
        """
        provider = model_config.provider.lower()
        model_id = model_config.model_id
        
        if provider not in self._model_providers:
            raise ValueError(f"Unsupported model provider: {provider}. Available: {list(self._model_providers.keys())}")
        
        # Validate that required environment variables are set
        try:
            _validate_provider_environment(provider, model_id)
        except ValueError as e:
            logger.error(f"Environment validation failed for {provider}/{model_id}: {e}")
            raise
        
        model_class = self._model_providers[provider]
        
        try:
            if provider == "litellm":
                # Check if this is an o3 model that needs parameter dropping
                is_o3_model = "o3" in model_id.lower()
                
                if is_o3_model:
                    # For o3 models, set global drop_params and create model normally
                    logger.info(f"🔧 Creating LiteLLM model for o3: {model_id} with global drop_params=True")
                    import litellm
                    litellm.drop_params = True  # Set globally for o3 models
                
                # Create LiteLLM instance - environment variables are already validated
                logger.info(f"🔧 Creating LiteLLM model: {model_id}")
                return model_class(id=model_id)
                
            elif provider == "openai":
                logger.info(f"🔧 Creating OpenAI model: {model_id}")
                return model_class(id=model_id)
                
            elif provider in ["fireworks", "fireworks_ai"]:
                logger.info(f"🔧 Creating Fireworks AI model: {model_id}")
                return model_class(id=model_id)
                
            else:
                # Generic instantiation
                logger.info(f"🔧 Creating {provider} model: {model_id}")
                return model_class(id=model_id)
                
        except Exception as e:
            logger.error(f"Failed to create model instance for {provider}/{model_id}: {e}")
            
            # Provide more specific error messages for common issues
            error_msg = str(e).lower()
            if "api key" in error_msg or "authentication" in error_msg or "unauthorized" in error_msg:
                raise ValueError(
                    f"Authentication failed for {provider}/{model_id}. "
                    f"Please verify your API key in .env file is correct and has the necessary permissions. "
                    f"Original error: {e}"
                ) from e
            elif "rate limit" in error_msg:
                raise ValueError(
                    f"Rate limit exceeded for {provider}/{model_id}. "
                    f"Please wait before retrying or check your API quota. "
                    f"Original error: {e}"
                ) from e
            elif "not found" in error_msg or "model" in error_msg:
                raise ValueError(
                    f"Model '{model_id}' not found or not accessible for provider '{provider}'. "
                    f"Please verify the model name is correct. "
                    f"Original error: {e}"
                ) from e
            else:
                raise ValueError(
                    f"Failed to create model instance for {provider}/{model_id}. "
                    f"Original error: {e}"
                ) from e
    
    def create_tools(self, tool_names: List[str]) -> List[Any]:
        """
        Create tool instances from tool names.
        
        Args:
            tool_names: List of tool names to instantiate
            
        Returns:
            List of tool instances
        """
        tools = []
        for tool_name in tool_names:
            if tool_name in self._tools:
                try:
                    tool_class = self._tools[tool_name]
                    tool_instance = tool_class()
                    tools.append(tool_instance)
                    logger.debug(f"Created tool: {tool_name}")
                except Exception as e:
                    logger.error(f"Failed to create tool {tool_name}: {e}")
                    # Continue with other tools
            else:
                logger.warning(f"Unknown tool: {tool_name}")
        return tools
    
    def create_agno_agent(self, agent_config: DictConfig) -> Optional[AgnoAgent]:
        """
        Create an AgnoAgent instance from configuration with proper structured output support.
        
        Args:
            agent_config: Agent configuration from YAML
            
        Returns:
            AgnoAgent instance or None for agents that don't use AgnoAgent
        """
        # Some agents (like custom search adapters) don't use AgnoAgent
        adapter_class_name = agent_config.get("adapter_class", "")
        if adapter_class_name in ["OpenAICustomSearchAdapter", "GeminiCustomSearchAdapter"]:
            logger.debug(f"Agent {agent_config.name} doesn't use AgnoAgent (custom search adapter)")
            return None
        
        if "model" not in agent_config or "prompt_source" not in agent_config:
            logger.debug(f"Agent {agent_config.name} doesn't use AgnoAgent (no model/prompt_source)")
            return None
        
        try:
            # Create model instance
            model = self.create_model_instance(agent_config.model)
            logger.debug(f"Created model for {agent_config.name}: {agent_config.model.provider}/{agent_config.model.model_id}")
            
            # Resolve system prompt
            system_message = self.config_loader.resolve_prompt(agent_config.prompt_source)
            logger.debug(f"Resolved prompt for {agent_config.name} from {agent_config.prompt_source}")
            
            # Get response model if specified
            response_model = None
            if "response_model" in agent_config:
                response_model_name = agent_config.response_model
                response_model = self.resolve_response_model(response_model_name)
                if response_model:
                    logger.debug(f"Using response model for {agent_config.name}: {response_model_name}")
                else:
                    logger.warning(f"Could not resolve response model {response_model_name} for {agent_config.name}")
            
            # Create tools if specified
            tools = []
            if "tools" in agent_config and agent_config.tools:
                tools = self.create_tools(agent_config.tools)
                if tools:
                    logger.debug(f"Created {len(tools)} tools for {agent_config.name}: {[type(t).__name__ for t in tools]}")
            
            # Prepare AgnoAgent kwargs
            agno_kwargs = {
                "model": model,
                "system_message": system_message,
                "name": f"{agent_config.name}_Agno",
            }
            
            # Add response model if specified
            if response_model:
                agno_kwargs["response_model"] = response_model
            
            # Add tools if available
            if tools:
                agno_kwargs["tools"] = tools
            
            # Handle additional AgnoAgent parameters from config
            if "agno_params" in agent_config:
                additional_params = dict(agent_config.agno_params)
                agno_kwargs.update(additional_params)
                logger.debug(f"Added additional AgnoAgent params for {agent_config.name}: {list(additional_params.keys())}")
            
            # Create AgnoAgent
            agno_agent = AgnoAgent(**agno_kwargs)
            
            logger.info(f"✅ Created AgnoAgent for {agent_config.name}")
            return agno_agent
            
        except Exception as e:
            logger.error(f"❌ Failed to create AgnoAgent for {agent_config.name}: {e}")
            raise
    
    def create_adapter(self, agent_config: DictConfig, agno_agent: Optional[AgnoAgent] = None) -> Any:
        """
        Create an adapter instance from configuration.
        
        Args:
            agent_config: Agent configuration from YAML
            agno_agent: Optional AgnoAgent instance
            
        Returns:
            Adapter instance
        """
        adapter_class_name = agent_config.adapter_class
        
        if adapter_class_name not in self._adapter_classes:
            raise ValueError(f"Unknown adapter class: {adapter_class_name}")
        
        adapter_class = self._adapter_classes[adapter_class_name]
        
        try:
            # Special handling for different adapter types
            if adapter_class_name in ["OpenAICustomSearchAdapter", "GeminiCustomSearchAdapter"]:
                # These adapters don't use AgnoAgent and have special initialization
                adapter_kwargs = {}
                
                # Check if there are custom parameters for this adapter
                if "adapter_params" in agent_config:
                    adapter_kwargs.update(dict(agent_config.adapter_params))
                
                # Override model_id if specified in config
                if "model" in agent_config and "model_id" in agent_config.model:
                    adapter_kwargs["model_id"] = agent_config.model.model_id
                
                return adapter_class(**adapter_kwargs)
                
            else:
                # Most adapters require an AgnoAgent instance
                if agno_agent is None:
                    raise ValueError(f"Adapter {adapter_class_name} requires an AgnoAgent instance")
                
                adapter_kwargs = {
                    "agno_agent_instance": agno_agent,
                    "agent_name": agent_config.name
                }
                
                # Add any additional adapter parameters from config
                if "adapter_params" in agent_config:
                    additional_params = dict(agent_config.adapter_params)
                    adapter_kwargs.update(additional_params)
                    logger.debug(f"Added additional adapter params for {agent_config.name}: {list(additional_params.keys())}")
                
                return adapter_class(**adapter_kwargs)
                
        except Exception as e:
            logger.error(f"❌ Failed to create adapter {adapter_class_name} for {agent_config.name}: {e}")
            raise
    
    def create_agent(self, agent_config: DictConfig) -> Dict[str, Any]:
        """
        Create a complete agent (AgnoAgent + Adapter) from configuration.
        
        Args:
            agent_config: Agent configuration from YAML
            
        Returns:
            Dictionary containing agent components and metadata
        """
        logger.info(f"🔧 Creating agent: {agent_config.name} (type: {agent_config.type})")
        
        try:
            # Create AgnoAgent if needed
            agno_agent = self.create_agno_agent(agent_config)
            
            # Create adapter
            adapter = self.create_adapter(agent_config, agno_agent)
            
            # CRITICAL FIX: Verify adapter is BaseAdapter
            if not isinstance(adapter, BaseAdapter):
                logger.error(f"❌ Created adapter for {agent_config.name} is not a BaseAdapter!")
                logger.error(f"   Type: {type(adapter)}")
                logger.error(f"   Expected: {BaseAdapter}")
                raise TypeError(f"Adapter {type(adapter)} is not a BaseAdapter")
            
            logger.info(f"✅ Created valid BaseAdapter for {agent_config.name}: {type(adapter).__name__}")
            
            # Prepare registration information
            registration_info = {
                "action_keys": [],
                "named_keys": []
            }
            
            if "registration" in agent_config:
                reg_config = agent_config.registration
                
                if "action_keys" in reg_config:
                    # Convert string task_types to TaskType enums
                    action_keys = []
                    for key in reg_config.action_keys:
                        action_verb = key.action_verb
                        task_type_value = key.get("task_type")
                        
                        # Convert string task_type to TaskType enum
                        if task_type_value is not None and isinstance(task_type_value, str):
                            try:
                                task_type_enum = TaskType[task_type_value.upper()]
                                action_keys.append((action_verb, task_type_enum))
                                logger.debug(f"Converted task_type '{task_type_value}' to enum {task_type_enum} for {agent_config.name}")
                            except KeyError:
                                logger.error(f"Invalid task_type '{task_type_value}' for agent {agent_config.name}. Valid values: {list(TaskType.__members__.keys())}")
                                raise ValueError(f"Invalid task_type: {task_type_value}")
                        else:
                            # task_type is None or already an enum
                            action_keys.append((action_verb, task_type_value))
                    
                    registration_info["action_keys"] = action_keys
                
                if "named_keys" in reg_config:
                    registration_info["named_keys"] = list(reg_config.named_keys)
            
            # Collect metadata about the agent
            metadata = {
                "has_structured_output": "response_model" in agent_config,
                "response_model": agent_config.get("response_model"),
                "has_tools": "tools" in agent_config and bool(agent_config.tools),
                "tools": list(agent_config.get("tools", [])),
                "model_info": dict(agent_config.model) if "model" in agent_config else None,
                "prompt_source": agent_config.get("prompt_source"),
            }
            
            agent_info = {
                "name": agent_config.name,
                "type": agent_config.type,
                "description": agent_config.get("description", ""),
                "adapter": adapter,
                "agno_agent": agno_agent,
                "registration": registration_info,
                "enabled": agent_config.get("enabled", True),
                "metadata": metadata,
                "config": agent_config
            }
            
            logger.info(f"✅ Successfully created agent: {agent_config.name}")
            if metadata["has_structured_output"]:
                logger.info(f"   📋 Structured output: {metadata['response_model']}")
            if metadata["has_tools"]:
                logger.info(f"   🔧 Tools: {metadata['tools']}")
            
            return agent_info
            
        except Exception as e:
            logger.error(f"❌ Failed to create agent {agent_config.name}: {e}")
            raise
    
    def create_all_agents(self, config: DictConfig) -> Dict[str, Dict[str, Any]]:
        """
        Create all agents from configuration.
        
        Args:
            config: Full configuration containing all agents
            
        Returns:
            Dictionary mapping agent names to agent info
        """
        agents = {}
        created_count = 0
        skipped_count = 0
        failed_count = 0
        
        logger.info(f"🚀 Creating {len(config.agents)} agents from configuration...")
        
        for agent_config in config.agents:
            try:
                # Skip disabled agents
                if not agent_config.get("enabled", True):
                    logger.info(f"⏭️  Skipping disabled agent: {agent_config.name}")
                    skipped_count += 1
                    continue
                
                # Create the agent
                agent_info = self.create_agent(agent_config)
                agents[agent_config.name] = agent_info
                created_count += 1
                
            except Exception as e:
                logger.error(f"❌ Failed to create agent {agent_config.name}: {e}")
                failed_count += 1
                # Continue with other agents rather than failing completely
                continue
        
        logger.info(f"📊 Agent creation summary:")
        logger.info(f"   ✅ Created: {created_count}")
        logger.info(f"   ⏭️  Skipped: {skipped_count}")
        logger.info(f"   ❌ Failed: {failed_count}")
        
        return agents

    def create_agents_for_profile(self, profile_config: 'DictConfig') -> Dict[str, Dict[str, Any]]:
        """
        Create agents specifically for a profile configuration.
        
        Args:
            profile_config: Profile configuration from YAML
            
        Returns:
            Dictionary of created agents
        """
        created_agents = {}
        
        # If the profile has its own agents section, create those
        if "agents" in profile_config and profile_config.agents:
            logger.info(f"Creating {len(profile_config.agents)} profile-specific agents...")
            
            for agent_config in profile_config.agents:
                if agent_config.get("enabled", True):
                    try:
                        agent_info = self.create_agent(agent_config)
                        created_agents[agent_config.name] = agent_info
                        logger.info(f"✅ Created profile agent: {agent_config.name}")
                    except Exception as e:
                        logger.error(f"❌ Failed to create profile agent {agent_config.name}: {e}")
        
        return created_agents

    def validate_blueprint_agents(self, blueprint: 'AgentBlueprint', agent_registry: AgentRegistry) -> Dict[str, Any]:
        """
        Validate that all agents referenced in a blueprint exist in the given registry instance.
        
        Args:
            blueprint: AgentBlueprint to validate.
            agent_registry: The AgentRegistry instance to check against.
            
        Returns:
            Validation results.
        """
        validation = {
            "valid": True,
            "missing_agents": [],
            "issues": [], # Added for consistency
            "available_agents": list(agent_registry.get_all_named_agents().keys()),
            "blueprint_agents": []
        }
        
        # Get all named agents from the instance
        named_agents = agent_registry.get_all_named_agents()

        # Check planners
        for task_type, planner_name in blueprint.planner_adapter_names.items():
            validation["blueprint_agents"].append(f"Planner({task_type.value}): {planner_name}")
            if planner_name not in named_agents:
                validation["missing_agents"].append(f"Planner: {planner_name}")
                validation["valid"] = False
        
        # Check executors
        for task_type, executor_name in blueprint.executor_adapter_names.items():
            validation["blueprint_agents"].append(f"Executor({task_type.value}): {executor_name}")
            if executor_name not in named_agents:
                validation["missing_agents"].append(f"Executor: {executor_name}")
                validation["valid"] = False
        
        # Check other agents
        other_agents = [
            ("Root Planner", blueprint.root_planner_adapter_name),
            ("Aggregator", blueprint.aggregator_adapter_name),
            ("Atomizer", blueprint.atomizer_adapter_name),
            ("PlanModifier", blueprint.plan_modifier_adapter_name),
            ("Default Planner", blueprint.default_planner_adapter_name),
            ("Default Executor", blueprint.default_executor_adapter_name),
        ]
        
        for agent_type, agent_name in other_agents:
            if agent_name:
                validation["blueprint_agents"].append(f"{agent_type}: {agent_name}")
                if agent_name not in named_agents:
                    validation["missing_agents"].append(f"{agent_type}: {agent_name}")
                    validation["valid"] = False
        
        if validation["missing_agents"]:
            validation["issues"].extend([
                f"Agent '{name}' referenced in blueprint '{blueprint.name}' is not registered."
                for name in validation["missing_agents"]
            ])

        return validation


def create_agents_from_config(config: DictConfig, config_loader) -> Dict[str, Dict[str, Any]]:
    """
    Convenience function to create all agents from configuration.
    
    Args:
        config: Configuration containing agent definitions
        config_loader: AgentConfigLoader instance
        
    Returns:
        Dictionary of created agents
    """
    factory = AgentFactory(config_loader)
    return factory.create_all_agents(config) 