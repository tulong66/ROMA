import os
import requests
import json
import types
import asyncio
import time
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

try:
    import wikipediaapi
except ImportError:
    logger.warning("Warning: wikipediaapi module not found. Wikipedia enhancement will not be available.")
    wikipediaapi = None

from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import (
    CustomSearcherOutput,
    AnnotationURLCitationModel,
    AgentTaskInput
)
from sentientresearchagent.hierarchical_agent_framework.agents.base_adapter import BaseAdapter

# Use TYPE_CHECKING to avoid circular imports
if TYPE_CHECKING:
    from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode
    from sentientresearchagent.hierarchical_agent_framework.tracing.manager import TraceManager

load_dotenv()

# Helper function to extract Wikipedia content
async def fetch_wikipedia_content(url: str) -> Optional[str]:
    """Fetch content from a Wikipedia URL using wikipediaapi."""
    if wikipediaapi is None:
        return None
    
    try:
        # Extract page title from URL
        # Handle different Wikipedia URL formats
        import re
        patterns = [
            r'wikipedia\.org/wiki/([^#?]+)',  # Standard wiki URL
            r'wikipedia\.org/.*[?&]title=([^&#]+)',  # URL with title parameter
        ]
        
        page_title = None
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                page_title = match.group(1).replace('_', ' ')
                break
        
        if not page_title:
            return None
        
        # Create Wikipedia API client
        wiki_wiki = wikipediaapi.Wikipedia(
            language='en',
            extract_format=wikipediaapi.ExtractFormat.WIKI,
            user_agent='SentientResearchAgent/1.0 (https://github.com/salzubi401/SentientResearchAgent)'
        )
        
        page = wiki_wiki.page(page_title)
        if page.exists():
            # Return summary + first section for manageable content
            content = f"Wikipedia: {page.title}\n\n{page.summary}\n\n"
            
            # Add section content if available
            sections = page.sections
            if sections:
                # Get first few sections (avoid overwhelming the context)
                for i, section in enumerate(sections[:3]):
                    if section.text:
                        content += f"\n## {section.title}\n{section.text}\n"
            
            return content
        else:
            return None
            
    except Exception as e:
        logger.warning(f"Error fetching Wikipedia content from {url}: {e}")
        return None

# --- OpenAI Custom Searcher with Annotations (Adapter Version) ---
class OpenAICustomSearchAdapter(BaseAdapter):
    """
    A direct adapter that uses OpenAI's gpt-4.1 (or similar) with the 
    'web_search_preview' tool to get answers with URL annotations.
    It does not use an underlying AgnoAgent.
    """
    adapter_name: str = "OpenAICustomSearchAdapter" 
    model_id: str = "gpt-4o" # Updated to use gpt-4o for better search results

    def __init__(self, openai_client = None, model_id: str = "gpt-4o"):
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

    async def process(self, node: TaskNode, agent_task_input: AgentTaskInput, trace_manager: "TraceManager") -> Dict:
        """
        Processes the task by extracting the goal as a query, calling OpenAI with
        web_search_preview using client.responses.create.
        Prioritizes response.output_text, and optionally parses nested text/annotations.
        """
        # Import trace_manager here to avoid circular imports
        from sentientresearchagent.hierarchical_agent_framework.tracing.manager import TraceManager
        
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

            # Expert searcher prompt for comprehensive data retrieval
            enhanced_query = f"""You are an expert data searcher with 20+ years of experience in searching and retrieving information from reliable sources with a keen eye for relevant data.

Your task is to RETRIEVE and FETCH all necessary data to answer the following query. Focus on data retrieval, not reasoning or analysis.

Guidelines:
1. COMPREHENSIVE DATA RETRIEVAL:
   - If it's a table, retrieve the ENTIRE table (even if it has 50, 100, or more rows)
   - If it's a list, include ALL items in the list
   - If it's statistics or rankings, include ALL available data points
   - For articles/paragraphs, include ALL relevant sections and mentions
   - Present data in its complete form - do not truncate or summarize

2. SOURCE RELIABILITY PRIORITY:
   - Wikipedia is the MOST PREFERRED source when available
   - Other reputable sources in order of preference:
     • Official government databases and statistics
     • Academic institutions and research papers
     • Established news organizations (BBC, Reuters, AP, etc.)
     • Industry-standard databases and professional organizations
   - Always cite your sources

3. DATA PRESENTATION:
   - Present data EXACTLY as found in the source
   - Maintain original formatting (tables, lists, etc.)
   - Include all columns, rows, and data points
   - Do NOT analyze, interpret, or reason about the data
   - Do NOT summarize or condense - present everything

QUERY: {query}

RETRIEVED DATA:"""
            
            api_response = await self.client.responses.create(
                model=self.model_id,
                tools=[{"type": "web_search_preview"}],
                input=enhanced_query
            )

            # 1. Prioritize getting api_response.output_text
            if hasattr(api_response, 'output_text') and api_response.output_text:
                raw_output = api_response.output_text
                
                # Post-process to extract just the retrieved data if it contains our prompt
                if "RETRIEVED DATA:" in raw_output:
                    # Extract everything after "RETRIEVED DATA:"
                    data_parts = raw_output.split("RETRIEVED DATA:", 1)
                    if len(data_parts) > 1:
                        output_text_with_citations = data_parts[1].strip()
                    else:
                        output_text_with_citations = raw_output
                else:
                    output_text_with_citations = raw_output
                    
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

            # Wikipedia API fetching disabled for now
            # Simply return the output without Wikipedia enhancement
            
            # Return a simple dictionary with a consistent key schema
            clean_output = {
                "query_used": query,
                "output_text": output_text_with_citations,
                "citations": [ann.dict() for ann in parsed_annotations]  # Include citations for transparency
            }

            main_output_preview = clean_output["output_text"][:150] + "..." if len(clean_output["output_text"]) > 150 else clean_output["output_text"]
            logger.success(f"  Adapter '{self.adapter_name}': Processed. Main output: '{main_output_preview}', Annotations: {len(parsed_annotations)}")
            node.output_type_description = "custom_searcher_output"
            
            # FIXED: Complete tracing stage with rich output
            # First update the stage with LLM response data
            trace_manager.update_stage(
                node_id=node.task_id,
                stage_name="execution",
                llm_response=clean_output["output_text"]
            )
            
            # Then complete the stage with output data
            trace_manager.complete_stage(
                node_id=node.task_id,
                stage_name="execution",
                output_data=clean_output
            )
            
            return clean_output

        except Exception as e:
            error_message = f"Error during {self.adapter_name} execution for node {node.task_id} (Query: {query}): {e}"
            logger.error(f"  Adapter Error: {error_message}")
            
            # FIXED: Complete tracing stage with error
            trace_manager.complete_stage(
                node_id=node.task_id,
                stage_name="execution",
                error=error_message
            )
            
            # Return a simple dictionary with the error
            return {
                "query_used": query,
                "output_text": f"API Call Failed: {e}"
            }


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
        
        # Create client with explicit API key - ensure we're creating a fresh client to avoid event loop issues
        try:
            self.client = gemini_client or genai.Client(api_key=api_key)
        except Exception as e:
            logger.error(f"Error creating Gemini client: {e}")
            raise
        
        self.model_id = model_id
        logger.info(f"Initialized {self.agent_name} with model: {self.model_id} (API key: {api_key[:10]}...{api_key[-4:]})")

    async def process(self, node: TaskNode, agent_task_input: AgentTaskInput, trace_manager: "TraceManager") -> Dict:
        """
        Processes the task by extracting the goal as a query, calling Gemini with
        google_search tool using client.aio.models.generate_content (async API).
        Parses response.text and grounding_metadata for citations.
        """
        # Import trace_manager here to avoid circular imports
        from sentientresearchagent.hierarchical_agent_framework.tracing.manager import TraceManager
        
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
            # Expert searcher prompt for comprehensive data retrieval
            enhanced_query = f"""You are an expert data searcher with 20+ years of experience in searching and retrieving information from reliable sources with a keen eye for relevant data.

Your task is to RETRIEVE and FETCH all necessary data to answer the following query. Focus on data retrieval, not reasoning or analysis.

Guidelines:
1. COMPREHENSIVE DATA RETRIEVAL:
   - If it's a table, retrieve the ENTIRE table (even if it has 50, 100, or more rows)
   - If it's a list, include ALL items in the list
   - If it's statistics or rankings, include ALL available data points
   - For articles/paragraphs, include ALL relevant sections and mentions
   - Present data in its complete form - do not truncate or summarize

2. SOURCE RELIABILITY PRIORITY:
   - Wikipedia is the MOST PREFERRED source when available
   - Other reputable sources in order of preference:
     • Official government databases and statistics
     • Academic institutions and research papers
     • Established news organizations (BBC, Reuters, AP, etc.)
     • Industry-standard databases and professional organizations
   - Always cite your sources

3. DATA PRESENTATION:
   - Present data EXACTLY as found in the source
   - Maintain original formatting (tables, lists, etc.)
   - Include all columns, rows, and data points
   - Do NOT analyze, interpret, or reason about the data
   - Do NOT summarize or condense - present everything

QUERY: {query}

RETRIEVED DATA:"""
            
            # Call Gemini API with Google Search tool using ASYNC API
            # Add better error handling for event loop issues and rate limiting
            max_retries = 3
            base_delay = 5.0
            
            for attempt in range(max_retries):
                try:
                    api_response = await self.client.aio.models.generate_content(
                        model=self.model_id,
                        contents=enhanced_query,
                        config={"tools": [{"google_search": {}}]},
                    )
                    break  # Success, exit retry loop
                
                except RuntimeError as e:
                    if "event loop" in str(e).lower():
                        # Event loop issue - try recreating the client
                        logger.warning(f"Event loop issue detected, recreating client: {e}")
                        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
                        self.client = genai.Client(api_key=api_key)
                        # Retry with new client
                        continue
                    else:
                        raise
                
                except Exception as e:
                    error_str = str(e).lower()
                    
                    # Handle rate limiting errors
                    if any(keyword in error_str for keyword in ['rate limit', '429', 'quota', 'throttle', 'exceeded']):
                        if attempt < max_retries - 1:
                            # Exponential backoff for rate limiting
                            delay = base_delay * (2 ** attempt) + (attempt * 10)  # Extra delay for rate limits
                            logger.warning(f"Rate limit hit (attempt {attempt + 1}/{max_retries}), retrying in {delay:.1f}s: {e}")
                            await asyncio.sleep(delay)
                            continue
                        else:
                            logger.error(f"Rate limit exceeded after {max_retries} attempts: {e}")
                            raise
                    
                    # Handle other API errors with shorter retry
                    elif any(keyword in error_str for keyword in ['timeout', 'connection', 'network', 'internal error']):
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)
                            logger.warning(f"API error (attempt {attempt + 1}/{max_retries}), retrying in {delay:.1f}s: {e}")
                            await asyncio.sleep(delay)
                            continue
                        else:
                            logger.error(f"API error after {max_retries} attempts: {e}")
                            raise
                    
                    # For other errors, don't retry
                    else:
                        raise

            # Check if api_response is None or has unexpected structure
            if api_response is None:
                logger.error(f"    {self.adapter_name}: API response is None")
                raise ValueError("API response is None")

            # 1. Get the main response text
            if hasattr(api_response, 'text') and api_response.text:
                raw_output = api_response.text
                
                # Post-process to extract just the retrieved data if it contains our prompt
                if "RETRIEVED DATA:" in raw_output:
                    # Extract everything after "RETRIEVED DATA:"
                    data_parts = raw_output.split("RETRIEVED DATA:", 1)
                    if len(data_parts) > 1:
                        output_text_with_citations = data_parts[1].strip()
                    else:
                        output_text_with_citations = raw_output
                else:
                    output_text_with_citations = raw_output
                
                parsed_text_content = output_text_with_citations  # Same content for both fields
                logger.success(f"    {self.adapter_name}: Retrieved response text (length: {len(output_text_with_citations)}).")
            else:
                logger.error(f"    {self.adapter_name}: 'text' not found or empty in API response. Main output will be error message.")
                logger.debug(f"    {self.adapter_name}: API response attributes: {dir(api_response) if api_response else 'None'}")
                # Keep the default error message for output_text_with_citations

            # 2. Parse grounding metadata for citations
            raw_annotations_data = []
            # Add more robust null checking to prevent NoneType iteration errors
            if (hasattr(api_response, 'candidates') and 
                api_response.candidates is not None and 
                isinstance(api_response.candidates, (list, tuple)) and
                len(api_response.candidates) > 0 and
                hasattr(api_response.candidates[0], 'grounding_metadata') and
                api_response.candidates[0].grounding_metadata is not None and
                hasattr(api_response.candidates[0].grounding_metadata, 'grounding_chunks') and
                api_response.candidates[0].grounding_metadata.grounding_chunks is not None):
                
                grounding_chunks = api_response.candidates[0].grounding_metadata.grounding_chunks
                
                # Additional safety check for grounding_chunks
                if isinstance(grounding_chunks, (list, tuple)):
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
                else:
                    logger.warning(f"    {self.adapter_name}: grounding_chunks is not iterable: {type(grounding_chunks)}")
                
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

            # Check for Wikipedia URLs in citations and enhance output
            wikipedia_contents = []
            if parsed_annotations:
                for ann in parsed_annotations:
                    if ann.url and 'wikipedia.org' in ann.url.lower():
                        logger.info(f"    {self.adapter_name}: Found Wikipedia citation: {ann.url}")
                        wiki_content = await fetch_wikipedia_content(ann.url)
                        if wiki_content:
                            wikipedia_contents.append(wiki_content)
                            logger.success(f"    {self.adapter_name}: Successfully fetched Wikipedia content for: {ann.title or ann.url}")
            
            # Enhance output with Wikipedia content if available
            enhanced_output_text = output_text_with_citations
            if wikipedia_contents:
                enhanced_output_text += "\n\n--- Additional Wikipedia Content ---\n\n"
                enhanced_output_text += "\n\n".join(wikipedia_contents)
                logger.info(f"    {self.adapter_name}: Enhanced output with {len(wikipedia_contents)} Wikipedia article(s)")
            
            # Return a simple dictionary with a consistent key schema
            clean_output = {
                "query_used": query,
                "output_text": enhanced_output_text,
                "citations": [ann.dict() for ann in parsed_annotations]  # Include citations for transparency
            }
            
            main_output_preview = clean_output["output_text"][:150] + "..." if len(clean_output["output_text"]) > 150 else clean_output["output_text"]
            logger.success(f"  Adapter '{self.adapter_name}': Processed. Main output: '{main_output_preview}', Citations processed: {len(parsed_annotations)}")
            node.output_type_description = "custom_searcher_output"
            
            # FIXED: Complete tracing stage with rich output
            trace_manager.update_stage(
                node_id=node.task_id,
                stage_name="execution",
                llm_response=clean_output["output_text"]
            )
            
            trace_manager.complete_stage(
                node_id=node.task_id,
                stage_name="execution",
                output_data=clean_output["output_text"]
            )
            
            return clean_output

        except Exception as e:
            error_message = f"Error during {self.adapter_name} execution for node {node.task_id} (Query: {query}): {e}"
            logger.error(f"  Adapter Error: {error_message}")
            
            trace_manager.complete_stage(
                node_id=node.task_id,
                stage_name="execution",
                error=error_message
            )
            
            # Return a simple dictionary with the error
            return {
                "query_used": query,
                "output_text": f"API Call Failed: {e}"
            }

