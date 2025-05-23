from flask import Flask, jsonify, request, make_response, send_file
from flask_cors import CORS # Import CORS
from flask_socketio import SocketIO, emit
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
import time
from threading import Timer

# Your project's core components
from sentientresearchagent.hierarchical_agent_framework.node.node_processor import NodeProcessor
from sentientresearchagent.hierarchical_agent_framework.graph.state_manager import StateManager
from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import KnowledgeStore
from sentientresearchagent.hierarchical_agent_framework.graph.execution_engine import ExecutionEngine
# Import NodeProcessorConfig from its new location
from sentientresearchagent.hierarchical_agent_framework.node.node_configs import NodeProcessorConfig
# Import HITLCoordinator
from sentientresearchagent.hierarchical_agent_framework.node.hitl_coordinator import HITLCoordinator
from sentientresearchagent.hierarchical_agent_framework.node.hitl_coordinator import HITLCoordinator

# --- Create a Flask App with SocketIO ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
CORS(app, origins=["http://localhost:3000"], methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], allow_headers=["Content-Type", "Authorization"], supports_credentials=True)

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="http://localhost:3000", async_mode='eventlet')

# --- Instantiate Core Backend Components ---
live_task_graph = TaskGraph()
live_knowledge_store = KnowledgeStore()
live_state_manager = StateManager(live_task_graph) 

# Instantiate NodeProcessorConfig first
node_processor_config = NodeProcessorConfig() 

# Instantiate HITLCoordinator
live_hitl_coordinator = HITLCoordinator(config=node_processor_config)

live_node_processor = NodeProcessor(
    task_graph=live_task_graph,
    knowledge_store=live_knowledge_store,
    config=node_processor_config 
)

live_execution_engine = ExecutionEngine(
    task_graph=live_task_graph,
    node_processor=live_node_processor,
    state_manager=live_state_manager,
    knowledge_store=live_knowledge_store,
    hitl_coordinator=live_hitl_coordinator # Pass HITLCoordinator
)

# Add a global variable to track update frequency
last_update_time = 0
UPDATE_THROTTLE = 2  # Send updates every 2 seconds maximum

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


# --- WebSocket Event Handlers ---
@socketio.on('connect')
def handle_connect():
    print('Client connected')
    # Send current graph state to newly connected client
    data = live_task_graph.to_visualization_dict()
    emit('task_graph_update', data)

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('start_project')
def handle_start_project(data):
    project_goal = data.get('project_goal')
    max_steps = data.get('max_steps', 250)
    
    if not project_goal:
        emit('error', {'message': 'project_goal not provided'})
        return
    
    print(f"Received WebSocket request to start project: '{project_goal}'")
    
    # Start the project execution in a background thread
    thread = threading.Thread(target=run_project_in_thread, args=(project_goal, max_steps))
    thread.daemon = True 
    thread.start()
    
    emit('project_started', {'message': f"Project '{project_goal}' initiated"})

# --- Function to broadcast graph updates ---
def broadcast_graph_update():
    """Broadcast current graph state to all connected clients with throttling"""
    global last_update_time
    current_time = time.time()
    
    # Throttle updates to avoid overwhelming the frontend
    if current_time - last_update_time < UPDATE_THROTTLE:
        return
        
    last_update_time = current_time
    data = live_task_graph.to_visualization_dict()
    print(f"Broadcasting graph update with {len(data.get('all_nodes', {}))} nodes")
    socketio.emit('task_graph_update', data)

# Add a function to force immediate updates
def force_broadcast_update():
    """Force an immediate broadcast regardless of throttling"""
    global last_update_time
    last_update_time = 0
    broadcast_graph_update()

# --- Modified async project execution (with broadcasts) ---
async def run_project_cycle_async(goal, max_steps):
    """Coroutine to run the project cycle with real-time updates."""
    print(f"Async task: Initializing project with goal: '{goal}'")
    try:
        live_task_graph.nodes.clear()
        live_task_graph.graphs.clear()
        live_task_graph.root_graph_id = None
        live_task_graph.overall_project_goal = None
        
        live_execution_engine.initialize_project(root_goal=goal)
        force_broadcast_update()  # Send initial state immediately
        
        print(f"Async task: Project initialized. Running cycle (max_steps={max_steps})...")
        
        # Start a timer to send periodic updates during execution
        def periodic_update():
            broadcast_graph_update()
            # Schedule next update
            Timer(3.0, periodic_update).start()
        
        # Start periodic updates
        Timer(3.0, periodic_update).start()
        
        await live_execution_engine.run_cycle(max_steps=max_steps)
        
        force_broadcast_update()  # Send final state
        print(f"Async task: run_cycle for goal '{goal}' completed.")
        
    except StopAgentRun as sae:
        print(f"Async task: Project execution stopped by user: {sae}")
        force_broadcast_update()
    except Exception as e:
        print(f"Async task: Error during project execution: {e}")
        force_broadcast_update()

def run_project_in_thread(goal, max_steps):
    """Target function for the thread, runs the asyncio event loop."""
    print(f"Thread: Starting asyncio event loop for project goal: '{goal}'")
    asyncio.run(run_project_cycle_async(goal, max_steps))
    print(f"Thread: Asyncio event loop for project goal: '{goal}' finished.")

# --- API Endpoint for Task Graph Data ---
@app.route('/api/task-graph', methods=['GET'])
def get_task_graph_data():
    """HTTP endpoint for task graph data (for compatibility)."""
    data = live_task_graph.to_visualization_dict()
    response = make_response(jsonify(data))
    response.headers['Access-Control-Allow-Origin'] = 'http://localhost:3000'
    return response

@app.route('/api/task-graph', methods=['OPTIONS']) # Add an OPTIONS handler
def handle_task_graph_options():
    response = make_response()
    response.headers['Access-Control-Allow-Origin'] = 'http://localhost:3000'
    response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.status_code = 204 # No Content for OPTIONS
    return response

# --- API Endpoint to Start a New Project ---
@app.route('/api/start-project', methods=['POST'])
def start_project():
    """HTTP endpoint to start project (for compatibility)."""
    data = request.get_json()
    if not data or 'project_goal' not in data:
        return jsonify({"error": "project_goal not provided"}), 400
    
    project_goal = data['project_goal']
    max_steps = data.get('max_steps', 250)
    
    thread = threading.Thread(target=run_project_in_thread, args=(project_goal, max_steps))
    thread.daemon = True 
    thread.start()
    
    return jsonify({"message": f"Project '{project_goal}' initiated"}), 202

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
    print("Flask-SocketIO server starting with live ExecutionEngine integration...")
    print("WebSocket available at http://localhost:5000")
    print("Frontend should connect at http://localhost:3000")
    
    # Run with SocketIO instead of regular Flask
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, use_reloader=False) 