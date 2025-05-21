from flask import Flask, jsonify, request, make_response, send_file
from flask_cors import CORS # Import CORS
from sentientresearchagent.hierarchical_agent_framework.graph.task_graph import TaskGraph
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskStatus, NodeType, TaskType
from datetime import datetime
import uuid # For generating unique IDs for sample data
import threading # For background execution
import io # For sending file in memory
import asyncio # Import asyncio
# PDF Generation - you'll need to install this: pip install markdown-pdf
from markdown_pdf import MarkdownPdf, Section # Using markdown-pdf library
from agno.exceptions import StopAgentRun # Import StopAgentRun

# Your project's core components
from sentientresearchagent.hierarchical_agent_framework.node.node_processor import NodeProcessor
from sentientresearchagent.hierarchical_agent_framework.graph.state_manager import StateManager
from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import KnowledgeStore
from sentientresearchagent.hierarchical_agent_framework.graph.execution_engine import ExecutionEngine
# Import NodeProcessorConfig from its new location
from sentientresearchagent.hierarchical_agent_framework.node.node_configs import NodeProcessorConfig

# --- Create a Flask App ---
app = Flask(__name__)
CORS(app, origins=["http://127.0.0.1:8080"], methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], allow_headers=["Content-Type", "Authorization"], supports_credentials=True)

# --- Instantiate Core Backend Components ---
# These will be shared and live for the duration of the server
# The TaskGraph instance here will be populated by the ExecutionEngine
live_task_graph = TaskGraph()
live_knowledge_store = KnowledgeStore()
live_state_manager = StateManager(live_task_graph) # StateManager needs the TaskGraph

# Instantiate NodeProcessor with required dependencies
node_processor_config = NodeProcessorConfig() # Example: using default config
live_node_processor = NodeProcessor(
    task_graph=live_task_graph,
    knowledge_store=live_knowledge_store,
    config=node_processor_config 
)

live_execution_engine = ExecutionEngine(
    task_graph=live_task_graph,
    node_processor=live_node_processor,
    state_manager=live_state_manager,
    knowledge_store=live_knowledge_store
)

def create_sample_task_graph():
    """Populates the global task_graph_instance with sample data for demonstration."""
    # Clear existing graph data if any, to avoid duplication on server restart with 'stat'
    live_task_graph.graphs.clear()
    live_task_graph.nodes.clear()
    live_task_graph.root_graph_id = None
    live_task_graph.overall_project_goal = "Test Markdown results and agent names."
    
    root_graph_id = "root_graph_" + str(uuid.uuid4())
    live_task_graph.add_graph(graph_id=root_graph_id, is_root=True)

    # Node 1 (Producer)
    node1_id = "task_producer_" + str(uuid.uuid4())
    node1_markdown_result = """
### Key Findings from Initial Research:
- **Paper A (2023):** Discusses the impact of X on Y.
  - *Key takeaway:* Significant correlation found.
- **Paper B (2022):** Focuses on Z.
  - `Code snippet example for Z analysis`
- **Statistics:**
  1. Metric 1: 75%
  2. Metric 2: Increased by 20%
"""
    node1 = TaskNode(
        task_id=node1_id,
        goal="Initial research and data gathering",
        task_type=TaskType.SEARCH,
        node_type=NodeType.EXECUTE,
        agent_name="WebSearchAgent_v1",
        layer=0,
        overall_objective=live_task_graph.overall_project_goal,
        status=TaskStatus.DONE,
        output_summary="Found 3 relevant papers and key statistics. See full result for details.",
        result=node1_markdown_result
    )
    live_task_graph.add_node_to_graph(root_graph_id, node1)

    # Node 2 (Consumer of context from Node 1, and a PLAN node)
    node2_id = "task_planner_consumer_" + str(uuid.uuid4())
    node2_input_payload = {
        "current_task_id": node2_id,
        "current_goal": "Plan main writing sections based on research",
        "current_task_type": TaskType.THINK.value, # Assuming string value needed by agent
        "overall_project_goal": live_task_graph.overall_project_goal,
        "relevant_context_items": [
            {
                "source_task_id": node1_id,
                "source_task_goal": node1.goal, # Goal of the task that produced this context
                "content": {"summary": node1.output_summary},
                "content_type_description": 'research_summary'
            }
        ]
    }
    node2_plan_result = { # Example of a structured (JSON) result
        "planTitle": "Main Writing Sections",
        "sections": [
            {"name": "Introduction", "points": ["Hook", "Thesis Statement", "Roadmap"]},
            {"name": "Body Paragraphs", "points": ["Topic Sentence 1", "Evidence 1", "Analysis 1"]},
            {"name": "Conclusion", "points": ["Restate Thesis", "Summarize", "Call to Action"]}
        ],
        "notes": "Ensure smooth transitions between sections."
    }
    node2 = TaskNode(
        task_id=node2_id,
        goal="Plan main writing sections based on research",
        task_type=TaskType.THINK,
        node_type=NodeType.PLAN,
        agent_name="HierarchicalPlannerAgent_v2",
        layer=0,
        overall_objective=live_task_graph.overall_project_goal,
        status=TaskStatus.DONE,
        output_summary="Planned 3 main sections. Full plan in details.",
        result=node2_plan_result,
        input_payload_dict=node2_input_payload
    )
    live_task_graph.add_node_to_graph(root_graph_id, node2)
    live_task_graph.add_edge(root_graph_id, node1_id, node2_id) # node2 depends on node1

    # Sub-graph for Node 2
    sub_graph_id = "sub_graph_for_" + node2_id
    node2.sub_graph_id = sub_graph_id
    live_task_graph.add_graph(graph_id=sub_graph_id)
    live_task_graph.nodes[node2_id] = node2 # Update node in map

    # Sub-node 1 (Potentially consumes context from its parent, Node 2)
    sub_node1_id = "task_sub1_" + str(uuid.uuid4())
    sub_node1_input_payload = {
        "current_task_id": sub_node1_id,
        "current_goal": "Draft Introduction using overall plan",
        "current_task_type": TaskType.WRITE.value,
        "overall_project_goal": live_task_graph.overall_project_goal,
        "relevant_context_items": [
            {"source_task_id": node2_id, "source_task_goal": node2.goal, "content_type_description": 'overall_plan'},
            {"source_task_id": node1_id, "source_task_goal": node1.goal, "content_type_description": 'research_summary'}
        ]
    }
    sub_node1 = TaskNode(
        task_id=sub_node1_id,
        goal="Draft Introduction using overall plan",
        task_type=TaskType.WRITE,
        node_type=NodeType.EXECUTE,
        agent_name="DraftingAgent_v1.2",
        layer=1,
        parent_node_id=node2_id,
        overall_objective=live_task_graph.overall_project_goal,
        status=TaskStatus.PENDING,
        input_payload_dict=sub_node1_input_payload,
        result="Introduction draft is pending..."
    )
    live_task_graph.add_node_to_graph(sub_graph_id, sub_node1)
    node2.planned_sub_task_ids.append(sub_node1_id)

    # Sub-node 2 (For simplicity, no complex context input here)
    sub_node2_id = "task_sub2_" + str(uuid.uuid4())
    sub_node2 = TaskNode(
        task_id=sub_node2_id,
        goal="Outline Body section",
        task_type=TaskType.THINK,
        node_type=NodeType.EXECUTE,
        agent_name="OutliningAgent_v1",
        layer=1,
        parent_node_id=node2_id,
        overall_objective=live_task_graph.overall_project_goal,
        status=TaskStatus.READY
        # input_payload_dict for sub_node2 could also be added
    )
    live_task_graph.add_node_to_graph(sub_graph_id, sub_node2)
    node2.planned_sub_task_ids.append(sub_node2_id)

    print("Sample task graph with Markdown results created.")


# --- API Endpoint for Task Graph Data ---
@app.route('/api/task-graph', methods=['GET'])
def get_task_graph_data():
    """Endpoint to get the LIVE task graph data for visualization."""
    if not live_task_graph.overall_project_goal and not live_task_graph.nodes:
        pass
    data = live_task_graph.to_visualization_dict()
    
    response = make_response(jsonify(data))
    response.headers['Access-Control-Allow-Origin'] = 'http://127.0.0.1:8080'
    response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response

@app.route('/api/task-graph', methods=['OPTIONS']) # Add an OPTIONS handler
def handle_task_graph_options():
    response = make_response()
    response.headers['Access-Control-Allow-Origin'] = 'http://127.0.0.1:8080'
    response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.status_code = 204 # No Content for OPTIONS
    return response

# --- API Endpoint to Start a New Project ---
async def run_project_cycle_async(goal, max_steps):
    """Coroutine to run the project cycle."""
    print(f"Async task: Initializing project with goal: '{goal}'")
    try:
        live_task_graph.nodes.clear()
        live_task_graph.graphs.clear()
        live_task_graph.root_graph_id = None
        live_task_graph.overall_project_goal = None
        
        live_execution_engine.initialize_project(root_goal=goal)
        print(f"Async task: Project initialized. Running cycle (max_steps={max_steps})...")
        await live_execution_engine.run_cycle(max_steps=max_steps)
        print(f"Async task: run_cycle for goal '{goal}' completed.")
    except StopAgentRun as sae: # Specifically catch StopAgentRun
        print(f"Async task: Project execution for goal '{goal}' was intentionally stopped by an agent or HITL: {sae.agent_message if hasattr(sae, 'agent_message') else str(sae)}")
        # Optionally update graph to reflect this user-driven stop
        if live_task_graph.root_graph_id and live_task_graph.get_node("root"):
            root_node = live_task_graph.get_node("root")
            if root_node.status not in [TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                 root_node.update_status(TaskStatus.CANCELLED, result_summary=f"Project stopped by user via HITL: {sae.agent_message if hasattr(sae, 'agent_message') else str(sae)}")
                 # You might need to manually trigger a knowledge store update if it's not automatic here
                 live_knowledge_store.add_or_update_record_from_node(root_node)
    except Exception as e:
        print(f"Async task: Error during project execution for goal '{goal}': {e}")
        # Optionally, update a global status or the graph itself to reflect the error
        if live_task_graph.root_graph_id and live_task_graph.get_node("root"):
            root_node = live_task_graph.get_node("root")
            if root_node.status not in [TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                root_node.update_status(TaskStatus.FAILED, error_msg=f"Project execution error: {str(e)}")
                live_knowledge_store.add_or_update_record_from_node(root_node)


def run_project_in_thread(goal, max_steps):
    """Target function for the thread, runs the asyncio event loop for the async task."""
    print(f"Thread: Starting asyncio event loop for project goal: '{goal}'")
    # The try-except block is now inside run_project_cycle_async for better context
    asyncio.run(run_project_cycle_async(goal, max_steps))
    print(f"Thread: Asyncio event loop for project goal: '{goal}' finished.")


@app.route('/api/start-project', methods=['POST'])
def start_project():
    data = request.get_json()
    if not data or 'project_goal' not in data:
        return jsonify({"error": "project_goal not provided"}), 400
    
    project_goal = data['project_goal']
    max_steps = data.get('max_steps', 250) 

    print(f"Received request to start project with goal: '{project_goal}', max_steps: {max_steps}")

    # Start the project execution in a background thread
    # The thread will run an asyncio event loop for our async function.
    thread = threading.Thread(target=run_project_in_thread, args=(project_goal, max_steps)) # Target the new sync wrapper
    thread.daemon = True 
    thread.start()

    return jsonify({"message": f"Project '{project_goal}' initiated. Graph will update in real-time."}), 202

@app.route('/api/download-report', methods=['GET'])
def download_report():
    """Endpoint to generate and download the final project report as PDF."""
    root_node_id = "root" # As defined in ExecutionEngine.initialize_project
    root_node = live_task_graph.get_node(root_node_id)

    if not root_node:
        return jsonify({"error": "Root node not found or project not initialized."}), 404

    if root_node.status != TaskStatus.DONE:
        return jsonify({"error": f"Root node is not yet DONE. Current status: {root_node.status.value}"}), 400

    markdown_content = root_node.result
    if not markdown_content or not isinstance(markdown_content, str):
        return jsonify({"error": "No markdown content found in the root node result or result is not a string."}), 404

    try:
        # Initialize MarkdownPdf
        # You can customize options like toc_level, optimize, etc.
        # pdf_converter = MarkdownPdf(toc_level=2, optimize=True)
        pdf_converter = MarkdownPdf() # Basic initialization

        # Add the markdown content as a section
        # The Section class can take user_css for styling, similar to WeasyPrint
        # For now, we'll use default styling.
        # Example with custom CSS:
        # custom_css = "body { font-family: sans-serif; } h1 { color: blue; }"
        # pdf_converter.add_section(Section(markdown_content), user_css=custom_css)
        pdf_converter.add_section(Section(markdown_content))
        
        # "Save" the PDF to an in-memory buffer
        pdf_buffer = io.BytesIO()
        pdf_converter.save(pdf_buffer)
        pdf_buffer.seek(0) # Reset buffer's position to the beginning
        
        # Send PDF as a file download
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"{live_task_graph.overall_project_goal or 'report'}.pdf"
        )

    except Exception as e:
        print(f"Error generating PDF with markdown-pdf: {e}")
        # Consider logging the traceback for more detailed error info
        # import traceback
        # print(traceback.format_exc())
        return jsonify({"error": f"Failed to generate PDF: {str(e)}"}), 500

# --- Main entry point to run the Flask app ---
if __name__ == '__main__':
    print("Flask server starting with live ExecutionEngine integration...")
    print("API available at http://127.0.0.1:5000/api/task-graph")
    print("Submit new projects via POST to http://127.0.0.1:5000/api/start-project")
    app.run(debug=True, use_reloader=False) # use_reloader=False is important when using threads with Flask's dev server 