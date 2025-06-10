import os
import requests
import json
import types
from dotenv import load_dotenv
from typing import Dict, Optional, List
from loguru import logger

try:
    from openai import OpenAI, AsyncOpenAI
except ImportError:
    logger.warning("Warning: openai module not found. OpenAICustomSearchAdapter will not be usable.")
    OpenAI = None
    AsyncOpenAI = None

from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import (
    CustomSearcherOutput,
    AnnotationURLCitationModel,
    AgentTaskInput
)
from sentientresearchagent.hierarchical_agent_framework.agents.base_adapter import BaseAdapter
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
        super().__init__(self.adapter_name) # Call parent constructor
        if AsyncOpenAI is None:
            raise ImportError("AsyncOpenAI client from openai library is not available. Please install or update 'openai'.")
        # Ensure the client passed or instantiated has the .responses.create method
        self.client = openai_client or AsyncOpenAI()
        self.model_id = model_id
        logger.info(f"Initialized {self.agent_name} with model: {self.model_id} (Async Client: {isinstance(self.client, AsyncOpenAI)})")

    async def process(self, node: TaskNode, agent_task_input: AgentTaskInput) -> CustomSearcherOutput:
        """
        Processes the task by extracting the goal as a query, calling OpenAI with
        web_search_preview using client.responses.create.
        Prioritizes response.output_text, and optionally parses nested text/annotations.
        """
        query = agent_task_input.current_goal
        logger.info(f"  Adapter '{self.adapter_name}': Processing node {node.task_id} (Query: '{query[:100]}...') with OpenAI model {self.model_id}")
        
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
            raw_annotations_data = [] # Define here to ensure it's always available
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
            return output

        except Exception as e:
            error_message = f"Error during {self.adapter_name} execution for node {node.task_id} (Query: {query}): {e}"
            logger.error(f"  Adapter Error: {error_message}")
            # Return a CustomSearcherOutput with the error message if the API call itself fails
            return CustomSearcherOutput(
                query_used=query,
                output_text_with_citations=f"API Call Failed: {e}",
                text_content=None,
                annotations=[]
            )

