from flask import Flask, jsonify, request, make_response, send_file
from flask_cors import CORS 
from flask_socketio import SocketIO, emit
from sentientresearchagent.hierarchical_agent_framework.graph.task_graph import TaskGraph
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskStatus, NodeType, TaskType
from datetime import datetime
import uuid 
import threading 
import io 
import asyncio 
import time
from agno.exceptions import StopAgentRun 

from sentientresearchagent.hierarchical_agent_framework.node.node_processor import NodeProcessor
from sentientresearchagent.hierarchical_agent_framework.graph.state_manager import StateManager
from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import KnowledgeStore
from sentientresearchagent.hierarchical_agent_framework.graph.execution_engine import ExecutionEngine
from sentientresearchagent.hierarchical_agent_framework.node.node_configs import NodeProcessorConfig
from sentientresearchagent.hierarchical_agent_framework.node.hitl_coordinator import HITLCoordinator

# --- Create Flask App ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
CORS(app, origins=["http://localhost:3000"], methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], allow_headers=["Content-Type", "Authorization"], supports_credentials=True)

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="http://localhost:3000", async_mode='eventlet')

# --- Initialize Components ---
live_task_graph = TaskGraph()
live_knowledge_store = KnowledgeStore()
live_state_manager = StateManager(live_task_graph) 
node_processor_config = NodeProcessorConfig() 
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
    hitl_coordinator=live_hitl_coordinator
)

print("✅ All components initialized successfully")

# --- Helper Functions ---
def broadcast_graph_update():
    """Send current graph state to all connected clients"""
    try:
        data = live_task_graph.to_visualization_dict()
        node_count = len(data.get('all_nodes', {}))
        print(f"📡 Broadcasting update: {node_count} nodes")
        socketio.emit('task_graph_update', data)
        return True
    except Exception as e:
        print(f"❌ Broadcast error: {e}")
        return False

# --- WebSocket Events ---
@socketio.on('connect')
def handle_connect():
    print('👋 Client connected')
    broadcast_graph_update()

@socketio.on('disconnect')
def handle_disconnect():
    print('👋 Client disconnected')

@socketio.on('start_project')
def handle_start_project(data):
    project_goal = data.get('project_goal')
    max_steps = data.get('max_steps', 250)
    
    if not project_goal:
        emit('error', {'message': 'project_goal not provided'})
        return
    
    print(f"🚀 Starting project: {project_goal}")
    
    # Start in background thread
    thread = threading.Thread(target=run_project_in_thread, args=(project_goal, max_steps))
    thread.daemon = True 
    thread.start()
    
    emit('project_started', {'message': f"Project started: {project_goal}"})

# --- Project Execution ---
async def run_project_cycle_async(goal, max_steps):
    """Run the project cycle"""
    print(f"🎯 Initializing project: {goal}")
    
    try:
        # Clear previous state
        live_task_graph.nodes.clear()
        live_task_graph.graphs.clear()
        live_task_graph.root_graph_id = None
        live_task_graph.overall_project_goal = None
        broadcast_graph_update()
        
        # Initialize project
        print("🚀 Calling initialize_project...")
        start_time = time.time()
        
        live_execution_engine.initialize_project(root_goal=goal)
        
        init_time = time.time() - start_time
        print(f"⏱️ Initialization took {init_time:.2f} seconds")
        
        # Send update after initialization
        broadcast_graph_update()
        print(f"📊 Initial state sent: {len(live_task_graph.nodes)} nodes")
        
        # Run execution cycle
        print("⚡ Starting execution...")
        await live_execution_engine.run_cycle(max_steps=max_steps)
        
        # Final update
        broadcast_graph_update()
        print("✅ Project completed")
        
    except Exception as e:
        print(f"❌ Project error: {e}")
        import traceback
        traceback.print_exc()
        broadcast_graph_update()

def run_project_in_thread(goal, max_steps):
    """Thread wrapper for async execution"""
    print(f"🧵 Thread started for: {goal}")
    try:
        asyncio.run(run_project_cycle_async(goal, max_steps))
    except Exception as e:
        print(f"❌ Thread error: {e}")
    print(f"🏁 Thread finished for: {goal}")

# --- HTTP Endpoints ---
@app.route('/api/task-graph', methods=['GET'])
def get_task_graph_data():
    """Get current graph data"""
    data = live_task_graph.to_visualization_dict()
    response = make_response(jsonify(data))
    response.headers['Access-Control-Allow-Origin'] = 'http://localhost:3000'
    return response

@app.route('/api/start-project', methods=['POST'])
def start_project():
    """HTTP endpoint to start project"""
    data = request.get_json()
    if not data or 'project_goal' not in data:
        return jsonify({"error": "project_goal not provided"}), 400
    
    project_goal = data['project_goal']
    max_steps = data.get('max_steps', 250)
    
    thread = threading.Thread(target=run_project_in_thread, args=(project_goal, max_steps))
    thread.daemon = True 
    thread.start()
    
    return jsonify({"message": f"Project '{project_goal}' initiated"}), 202

# --- Main Entry Point ---
if __name__ == '__main__':
    print("🚀 Starting Flask-SocketIO server...")
    print("📡 WebSocket: http://localhost:5000")
    print("🌐 Frontend: http://localhost:3000")
    
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, use_reloader=False)