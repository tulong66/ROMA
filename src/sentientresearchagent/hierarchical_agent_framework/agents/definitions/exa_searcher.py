"""
Exa Custom Searcher Adapter - Uses Exa API for search and LiteLLM for processing results.
"""

import os
import asyncio
from typing import Dict, List, Optional, TYPE_CHECKING
from loguru import logger
from dotenv import load_dotenv

try:
    from exa_py import Exa
except ImportError:
    logger.warning("Warning: exa_py module not found. ExaCustomSearchAdapter will not be usable.")
    Exa = None

try:
    from litellm import acompletion
except ImportError:
    logger.warning("Warning: litellm module not found. ExaCustomSearchAdapter will not be usable.")
    acompletion = None

from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import (
    AnnotationURLCitationModel,
    AgentTaskInput
)
from sentientresearchagent.hierarchical_agent_framework.agents.base_adapter import BaseAdapter
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode

if TYPE_CHECKING:
    from sentientresearchagent.hierarchical_agent_framework.tracing.manager import TraceManager

load_dotenv()


class ExaCustomSearchAdapter(BaseAdapter):
    """
    A direct adapter that uses Exa API for search and LiteLLM for processing results.
    Retrieves comprehensive data from multiple sources and formats them for LLM processing.
    """
    adapter_name: str = "ExaCustomSearchAdapter"
    model_id: str = "gpt-4o"  # Default model for LiteLLM, can be configured

    def __init__(self, exa_client=None, model_id: str = "gpt-4o", num_results: int = 5, **kwargs):
        super().__init__(self.adapter_name)
        
        if Exa is None:
            raise ImportError("exa_py module is not available. Please install 'exa-py'.")
        if acompletion is None:
            raise ImportError("litellm module is not available. Please install 'litellm'.")
        
        # Get API key
        api_key = os.getenv("EXA_API_KEY")
        if not api_key:
            raise ValueError("EXA_API_KEY environment variable is required for ExaCustomSearchAdapter")
        
        # Create Exa client
        self.exa_client = exa_client or Exa(api_key=api_key)
        self.model_id = model_id
        self.num_results = num_results
        
        # Store any additional parameters for future use
        self.additional_params = kwargs
        
        logger.info(f"Initialized {self.agent_name} with model: {self.model_id} and num_results: {self.num_results}")

    async def process(self, node: TaskNode, agent_task_input: AgentTaskInput, trace_manager: "TraceManager") -> Dict:
        """
        Processes the task by:
        1. Using Exa API to search for relevant content
        2. Formatting results with source separators
        3. Using LiteLLM to extract and present comprehensive data
        """
        from sentientresearchagent.hierarchical_agent_framework.tracing.manager import TraceManager
        
        query = agent_task_input.current_goal
        logger.info(f"  Adapter '{self.adapter_name}': Processing node {node.task_id} (Query: '{query[:100]}...') with Exa search")
        
        # Start tracing stage
        trace_manager.start_stage(
            node_id=node.task_id,
            stage_name="execution",
            agent_name=self.adapter_name,
            adapter_name=self.__class__.__name__,
            user_input=query,
            model_info={"model": self.model_id, "provider": "litellm"}
        )
        
        try:
            # Step 1: Search using Exa
            logger.info(f"    {self.adapter_name}: Searching with Exa API...")
            
            # Use search_and_contents to get both search results and content
            exa_results = await asyncio.to_thread(
                self.exa_client.search_and_contents,
                query,
                text=True,
                num_results=self.num_results,
                context=True  # Include context for better understanding
            )
            
            if not exa_results or not exa_results.results:
                logger.warning(f"    {self.adapter_name}: No results found from Exa search")
                return {
                    "query_used": query,
                    "output_text": "No results found for the given query."
                }
            
            logger.success(f"    {self.adapter_name}: Retrieved {len(exa_results.results)} results from Exa")
            
            # Step 2: Format results with separators
            formatted_sources = []
            citations = []
            
            for i, result in enumerate(exa_results.results):
                # Extract relevant fields
                title = getattr(result, 'title', f'Source {i+1}')
                url = getattr(result, 'url', '')
                text = getattr(result, 'text', '')
                published_date = getattr(result, 'published_date', None)
                
                # Format source with separators
                source_content = f"-------------START OF SOURCE {i+1}-------------\n"
                source_content += f"Title: {title}\n"
                source_content += f"URL: {url}\n"
                if published_date:
                    source_content += f"Published: {published_date}\n"
                source_content += f"\nContent:\n{text}\n"
                source_content += f"-------------END OF SOURCE {i+1}-------------"
                
                formatted_sources.append(source_content)
                
                # Add to citations
                citations.append({
                    'title': title,
                    'url': url,
                    'start_index': 0,
                    'end_index': len(text),
                    'type': 'url_citation'
                })
            
            # Step 3: Create system prompt for LiteLLM
            system_prompt = """You are an expert data extraction and presentation assistant. Your task is to process multiple sources and present data in the most concise and thorough form relevant to the query.

CRITICAL GUIDELINES:

1. SOURCE RELIABILITY HIERARCHY:
   - MOST PREFERRED: Wikipedia, official government websites (.gov), academic institutions (.edu)
   - HIGHLY TRUSTED: Established news organizations (BBC, Reuters, AP, etc.), official organization websites
   - TRUSTED: Industry publications, research papers, reputable databases
   - USE WITH CAUTION: Blogs, forums, social media (only if no better sources available)
   - When conflicting information exists, ALWAYS prioritize the most reliable source

2. COMPREHENSIVE DATA EXTRACTION:
   - Extract EVERYTHING related to the query from ALL sources
   - If there's a table with 50+ entries, include ALL 50+ entries
   - If there's a list, include ALL items
   - If there's statistics or rankings, include ALL data points
   - NEVER truncate, summarize, or omit data

3. SOURCE PRIORITIZATION:
   - First prioritize by reliability (Wikipedia > Government > Academic > News)
   - Then prioritize more recent sources over older ones within the same reliability tier
   - Clearly indicate which data comes from which source when relevant
   - If multiple sources provide the same data, mention it once but note all sources

4. DATA PRESENTATION:
   - Present data in its most useful format (tables, lists, structured text)
   - Maintain clarity and organization
   - Include ALL numerical data, dates, names, and specific details
   - Preserve exact values, percentages, and statistics
   - Always cite the most reliable source for each piece of information

5. COMPLETENESS OVER BREVITY:
   - Always prioritize including MORE information rather than less
   - It's better to include potentially relevant data than to exclude it
   - When in doubt, include it

6. SOURCE AWARENESS:
   - Sources are separated by markers like "-------------START OF SOURCE X-------------"
   - Process ALL sources thoroughly
   - Do not mention the source markers in your output
   - Cite sources naturally within the text when presenting data

Remember: Your primary goal is to be THOROUGH and COMPLETE while prioritizing the most RELIABLE sources. Users need ALL the data from trustworthy sources."""

            # Step 4: Combine all sources
            all_sources = "\n\n".join(formatted_sources)
            
            # Step 5: Create user prompt
            user_prompt = f"""Query: {query}

Below are {len(formatted_sources)} sources with relevant information. Extract and present ALL data related to the query:

{all_sources}

IMPORTANT: Include EVERY piece of relevant data from ALL sources. Do not summarize or truncate."""

            # Step 6: Call LiteLLM
            logger.info(f"    {self.adapter_name}: Processing sources with LiteLLM model {self.model_id}...")
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            # Use acompletion for async call
            llm_response = await acompletion(
                model=self.model_id,
                messages=messages,
                temperature=0.1,  # Low temperature for factual accuracy
                max_tokens=4000   # Allow for comprehensive responses
            )
            
            # Extract the response text
            output_text = llm_response.choices[0].message.content
            
            logger.success(f"    {self.adapter_name}: Successfully processed {len(formatted_sources)} sources")
            
            # Return formatted output matching other searchers
            clean_output = {
                "query_used": query,
                "output_text": output_text,
                "citations": [ann if isinstance(ann, dict) else ann.dict() for ann in citations]  # Ensure proper format
            }
            
            # Update and complete tracing
            trace_manager.update_stage(
                node_id=node.task_id,
                stage_name="execution",
                llm_response=output_text
            )
            
            trace_manager.complete_stage(
                node_id=node.task_id,
                stage_name="execution",
                output_data=clean_output
            )
            
            node.output_type_description = "custom_searcher_output"
            
            return clean_output
            
        except Exception as e:
            error_message = f"Error during {self.adapter_name} execution for node {node.task_id} (Query: {query}): {e}"
            logger.error(f"  Adapter Error: {error_message}")
            
            trace_manager.complete_stage(
                node_id=node.task_id,
                stage_name="execution",
                error=error_message
            )
            
            return {
                "query_used": query,
                "output_text": f"Search Failed: {e}"
            }