import os
import requests
import json
import types
from dotenv import load_dotenv
from typing import Dict, Optional, List, TYPE_CHECKING
from loguru import logger
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode

try:
    from openai import OpenAI, AsyncOpenAI
except ImportError:
    logger.warning("Warning: openai module not found. OpenAICustomSearchAdapter will not be usable.")
    OpenAI = None
    AsyncOpenAI = None

try:
    from google import genai
    from google.genai.types import Tool, GenerateContentConfig, GoogleSearch
except ImportError:
    logger.warning("Warning: google-genai module not found. GeminiCustomSearchAdapter will not be usable.")
    genai = None

from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import (
    CustomSearcherOutput,
    AnnotationURLCitationModel,
    AgentTaskInput
)
from sentientresearchagent.hierarchical_agent_framework.agents.base_adapter import BaseAdapter

# Use TYPE_CHECKING to avoid circular imports
if TYPE_CHECKING:
    from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode

load_dotenv()

# --- OpenAI Custom Searcher with Annotations (Adapter Version) ---
class OpenAICustomSearchAdapter(BaseAdapter):
    """
    A direct adapter that uses OpenAI's gpt-4.1 (or similar) with the 
    'web_search_preview' tool to get answers with URL annotations.
    It does not use an underlying AgnoAgent.
    """
    adapter_name: str = "OpenAICustomSearchAdapter" 
    model_id: str = "gpt-4.1" # As per your example, can be configured

    def __init__(self, openai_client = None, model_id: str = "gpt-4.1"):
        super().__init__(self.adapter_name)
        if AsyncOpenAI is None:
            raise ImportError("AsyncOpenAI client from openai library is not available. Please install or update 'openai'.")
        
        # Debug: Let's see what environment variables are actually set
        api_key = os.getenv("OPENAI_API_KEY")
        logger.info(f"🔍 DEBUG: OPENAI_API_KEY from os.getenv: {api_key[:10] if api_key else 'None'}...{api_key[-4:] if api_key and len(api_key) > 10 else ''}")
        
        # Also check if there are any other OpenAI-related env vars
        for key, value in os.environ.items():
            if "OPENAI" in key.upper():
                logger.info(f"🔍 DEBUG: Found env var {key}: {value[:10] if value else 'None'}...{value[-4:] if value and len(value) > 10 else ''}")
        
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required for OpenAICustomSearchAdapter")
        
        # Create client with explicit API key
        self.client = openai_client or AsyncOpenAI(api_key=api_key)
        self.model_id = model_id
        logger.info(f"Initialized {self.agent_name} with model: {self.model_id} (API key: {api_key[:10]}...{api_key[-4:]})")

    async def process(self, node: TaskNode, agent_task_input: AgentTaskInput) -> CustomSearcherOutput:
        """
        Processes the task by extracting the goal as a query, calling OpenAI with
        web_search_preview using client.responses.create.
        Prioritizes response.output_text, and optionally parses nested text/annotations.
        """
        # Import trace_manager here to avoid circular imports
        from sentientresearchagent.hierarchical_agent_framework.tracing.manager import trace_manager
        
        query = agent_task_input.current_goal
        logger.info(f"  Adapter '{self.adapter_name}': Processing node {node.task_id} (Query: '{query[:100]}...') with OpenAI model {self.model_id}")
        
        # Start tracing stage
        trace_manager.start_stage(
            node_id=node.task_id,
            stage_name="execution",
            agent_name=self.adapter_name,
            adapter_name=self.__class__.__name__,
            user_input=query,
            model_info={"model": self.model_id, "provider": "openai"}
        )
        
        output_text_with_citations = f"Error: Could not retrieve output_text for query: {query}" # Default error
        parsed_text_content: Optional[str] = None
        parsed_annotations: List[AnnotationURLCitationModel] = []

        try:
            # Ensure client is async and has responses.create
            if not isinstance(self.client, AsyncOpenAI) or not hasattr(self.client.responses, 'create'):
                 logger.error(f"  {self.adapter_name}: Invalid OpenAI client. Expected AsyncOpenAI with responses.create. Got: {type(self.client)}")
                 raise TypeError("Invalid OpenAI client setup for async operation.")

            api_response = await self.client.responses.create(
                model=self.model_id,
                tools=[{"type": "web_search_preview"}],
                input=query
            )

            # 1. Prioritize getting api_response.output_text
            if hasattr(api_response, 'output_text') and api_response.output_text:
                output_text_with_citations = api_response.output_text
                logger.success(f"    {self.adapter_name}: Retrieved 'output_text' (length: {len(output_text_with_citations)}).")
            else:
                logger.error(f"    {self.adapter_name}: 'output_text' not found or empty in API response. Main output will be error message.")
                # Keep the default error message for output_text_with_citations

            # 2. Attempt to parse nested text_content and annotations as supplementary info
            raw_annotations_data = []
            if hasattr(api_response, 'output') and \
               isinstance(api_response.output, list) and \
               len(api_response.output) > 1 and \
               hasattr(api_response.output[1], 'content') and \
               isinstance(api_response.output[1].content, list) and \
               len(api_response.output[1].content) > 0:
                
                content_item = api_response.output[1].content[0]
                
                if hasattr(content_item, 'text') and content_item.text:
                    parsed_text_content = content_item.text
                    logger.success(f"    {self.adapter_name}: Retrieved nested 'text_content' (length: {len(parsed_text_content)}).")
                else:
                    logger.warning(f"    {self.adapter_name}: Nested 'text' attribute not found or empty.")

                if hasattr(content_item, 'annotations') and isinstance(content_item.annotations, list):
                    temp_raw_annotations = []
                    for ann_obj in content_item.annotations:
                        ann_dict = {
                            'title': getattr(ann_obj, 'title', None),
                            'url': getattr(ann_obj, 'url', None),
                            'start_index': getattr(ann_obj, 'start_index', -1),
                            'end_index': getattr(ann_obj, 'end_index', -1),
                            'type': getattr(ann_obj, 'type', 'url_citation')
                        }
                        if ann_dict['url'] and ann_dict['start_index'] != -1 and ann_dict['end_index'] != -1:
                            temp_raw_annotations.append(ann_dict)
                        else:
                            logger.warning(f"    {self.adapter_name}: Skipping invalid nested annotation object: {ann_obj}")
                    
                    if temp_raw_annotations:
                        raw_annotations_data = temp_raw_annotations # Assign if we got valid annotations
                        logger.success(f"    {self.adapter_name}: Retrieved {len(raw_annotations_data)} nested 'annotations'.")
                else:
                    logger.warning(f"    {self.adapter_name}: Nested 'annotations' attribute not found or not a list.")
            else:
                logger.warning(f"    {self.adapter_name}: Nested API response structure 'output[1].content[0]' not found. No supplementary text/annotations.")

            for ann_data in raw_annotations_data:
                try:
                    parsed_annotations.append(AnnotationURLCitationModel(**ann_data))
                except Exception as e_pydantic:
                    logger.warning(f"    {self.adapter_name}: Error parsing an annotation dict: {ann_data}, Error: {e_pydantic}")

            output = CustomSearcherOutput(
                query_used=query,
                output_text_with_citations=output_text_with_citations,
                text_content=parsed_text_content,
                annotations=parsed_annotations
            )
            
            main_output_preview = output.output_text_with_citations[:150] + "..." if len(output.output_text_with_citations) > 150 else output.output_text_with_citations
            logger.success(f"  Adapter '{self.adapter_name}': Processed. Main output: '{main_output_preview}', Annotations: {len(output.annotations)}")
            node.output_type_description = "custom_searcher_output_with_citations"
            
            # FIXED: Complete tracing stage with rich output
            # First update the stage with LLM response data
            trace_manager.update_stage(
                node_id=node.task_id,
                stage_name="execution",
                llm_response=output.output_text_with_citations
            )
            
            # Then complete the stage with output data
            trace_manager.complete_stage(
                node_id=node.task_id,
                stage_name="execution",
                output_data=output.output_text_with_citations
            )
            
            return output

        except Exception as e:
            error_message = f"Error during {self.adapter_name} execution for node {node.task_id} (Query: {query}): {e}"
            logger.error(f"  Adapter Error: {error_message}")
            
            # FIXED: Complete tracing stage with error
            trace_manager.complete_stage(
                node_id=node.task_id,
                stage_name="execution",
                error=error_message
            )
            
            # Return a CustomSearcherOutput with the error message if the API call itself fails
            return CustomSearcherOutput(
                query_used=query,
                output_text_with_citations=f"API Call Failed: {e}",
                text_content=None,
                annotations=[]
            )


# --- Gemini Custom Searcher with Annotations (Adapter Version) ---
class GeminiCustomSearchAdapter(BaseAdapter):
    """
    A direct adapter that uses Google Gemini with Google Search tool to get answers with URL annotations.
    It does not use an underlying AgnoAgent.
    """
    adapter_name: str = "GeminiCustomSearchAdapter" 
    model_id: str = "gemini-2.5-flash" # As per your example, can be configured

    def __init__(self, gemini_client = None, model_id: str = "gemini-2.5-flash"):
        super().__init__(self.adapter_name)
        if genai is None:
            raise ImportError("google-genai module is not available. Please install 'google-genai'.")
        
        # Debug: Let's see what environment variables are actually set
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        logger.info(f"🔍 DEBUG: GOOGLE_API_KEY/GEMINI_API_KEY from os.getenv: {api_key[:10] if api_key else 'None'}...{api_key[-4:] if api_key and len(api_key) > 10 else ''}")
        
        # Also check if there are any other Google/Gemini-related env vars
        for key, value in os.environ.items():
            if "GOOGLE" in key.upper() or "GEMINI" in key.upper():
                logger.info(f"🔍 DEBUG: Found env var {key}: {value[:10] if value else 'None'}...{value[-4:] if value and len(value) > 10 else ''}")
        
        if not api_key:
            raise ValueError("GOOGLE_API_KEY or GEMINI_API_KEY environment variable is required for GeminiCustomSearchAdapter")
        
        # Create client with explicit API key
        self.client = gemini_client or genai.Client(api_key=api_key)
        self.model_id = model_id
        logger.info(f"Initialized {self.agent_name} with model: {self.model_id} (API key: {api_key[:10]}...{api_key[-4:]})")

    async def process(self, node: TaskNode, agent_task_input: AgentTaskInput) -> CustomSearcherOutput:
        """
        Processes the task by extracting the goal as a query, calling Gemini with
        google_search tool using client.aio.models.generate_content (async API).
        Parses response.text and grounding_metadata for citations.
        """
        # Import trace_manager here to avoid circular imports
        from sentientresearchagent.hierarchical_agent_framework.tracing.manager import trace_manager
        
        query = agent_task_input.current_goal
        logger.info(f"  Adapter '{self.adapter_name}': Processing node {node.task_id} (Query: '{query[:100]}...') with Gemini model {self.model_id}")
        
        # Start tracing stage
        trace_manager.start_stage(
            node_id=node.task_id,
            stage_name="execution",
            agent_name=self.adapter_name,
            adapter_name=self.__class__.__name__,
            user_input=query,
            model_info={"model": self.model_id, "provider": "google_gemini"}
        )
        
        output_text_with_citations = f"Error: Could not retrieve output_text for query: {query}" # Default error
        parsed_text_content: Optional[str] = None
        parsed_annotations: List[AnnotationURLCitationModel] = []

        try:
            # Call Gemini API with Google Search tool using ASYNC API
            api_response = await self.client.aio.models.generate_content(
                model=self.model_id,
                contents=query,
                config={"tools": [{"google_search": {}}]},
            )

            # 1. Get the main response text
            if hasattr(api_response, 'text') and api_response.text:
                output_text_with_citations = api_response.text
                parsed_text_content = api_response.text  # Same content for both fields
                logger.success(f"    {self.adapter_name}: Retrieved response text (length: {len(output_text_with_citations)}).")
            else:
                logger.error(f"    {self.adapter_name}: 'text' not found or empty in API response. Main output will be error message.")
                # Keep the default error message for output_text_with_citations

            # 2. Parse grounding metadata for citations
            raw_annotations_data = []
            if (hasattr(api_response, 'candidates') and 
                api_response.candidates and 
                len(api_response.candidates) > 0 and
                hasattr(api_response.candidates[0], 'grounding_metadata') and
                hasattr(api_response.candidates[0].grounding_metadata, 'grounding_chunks')):
                
                grounding_chunks = api_response.candidates[0].grounding_metadata.grounding_chunks
                
                for i, chunk in enumerate(grounding_chunks):
                    if hasattr(chunk, 'web') and chunk.web:
                        web_info = chunk.web
                        ann_dict = {
                            'title': getattr(web_info, 'title', f"Source {i+1}"),
                            'url': getattr(web_info, 'uri', None),
                            'start_index': 0,  # Gemini doesn't provide exact indices, so we'll use defaults
                            'end_index': len(output_text_with_citations) if output_text_with_citations else 0,
                            'type': 'url_citation'
                        }
                        
                        if ann_dict['url']:
                            raw_annotations_data.append(ann_dict)
                        else:
                            logger.warning(f"    {self.adapter_name}: Skipping grounding chunk without URL: {chunk}")
                
                if raw_annotations_data:
                    logger.success(f"    {self.adapter_name}: Retrieved {len(raw_annotations_data)} grounding citations.")
            else:
                logger.warning(f"    {self.adapter_name}: No grounding metadata found in API response.")

            # Convert to AnnotationURLCitationModel objects
            for ann_data in raw_annotations_data:
                try:
                    parsed_annotations.append(AnnotationURLCitationModel(**ann_data))
                except Exception as e_pydantic:
                    logger.warning(f"    {self.adapter_name}: Error parsing an annotation dict: {ann_data}, Error: {e_pydantic}")

            output = CustomSearcherOutput(
                query_used=query,
                output_text_with_citations=output_text_with_citations,
                text_content=parsed_text_content,
                annotations=parsed_annotations
            )
            
            main_output_preview = output.output_text_with_citations[:150] + "..." if len(output.output_text_with_citations) > 150 else output.output_text_with_citations
            logger.success(f"  Adapter '{self.adapter_name}': Processed. Main output: '{main_output_preview}', Annotations: {len(output.annotations)}")
            node.output_type_description = "custom_searcher_output_with_citations"
            
            # Complete tracing stage with rich output
            trace_manager.update_stage(
                node_id=node.task_id,
                stage_name="execution",
                llm_response=output.output_text_with_citations
            )
            
            trace_manager.complete_stage(
                node_id=node.task_id,
                stage_name="execution",
                output_data=output.output_text_with_citations
            )
            
            return output

        except Exception as e:
            error_message = f"Error during {self.adapter_name} execution for node {node.task_id} (Query: {query}): {e}"
            logger.error(f"  Adapter Error: {error_message}")
            
            # Complete tracing stage with error
            trace_manager.complete_stage(
                node_id=node.task_id,
                stage_name="execution",
                error=error_message
            )
            
            # Return a CustomSearcherOutput with the error message if the API call itself fails
            return CustomSearcherOutput(
                query_used=query,
                output_text_with_citations=f"API Call Failed: {e}",
                text_content=None,
                annotations=[]
            )

