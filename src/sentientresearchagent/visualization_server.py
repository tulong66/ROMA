from flask import Flask, jsonify, request, make_response, send_file
from flask_cors import CORS 
from flask_socketio import SocketIO, emit
import threading 
import asyncio 
import time
import traceback
import sys
from agno.exceptions import StopAgentRun 

# NEW: Import from our consolidated systems
from sentientresearchagent.hierarchical_agent_framework.graph.task_graph import TaskGraph
from sentientresearchagent.hierarchical_agent_framework.types import TaskStatus, NodeType, TaskType
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode
from sentientresearchagent.hierarchical_agent_framework.node.node_processor import NodeProcessor
from sentientresearchagent.hierarchical_agent_framework.graph.state_manager import StateManager
from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import KnowledgeStore
from sentientresearchagent.hierarchical_agent_framework.graph.execution_engine import ExecutionEngine
from sentientresearchagent.hierarchical_agent_framework.node.node_configs import NodeProcessorConfig
from sentientresearchagent.hierarchical_agent_framework.node.hitl_coordinator import HITLCoordinator

# NEW: Import our new systems
from sentientresearchagent.config import load_config, create_sample_config
from sentientresearchagent.config_utils import auto_load_config, validate_config
from sentientresearchagent.cache.cache_manager import init_cache_manager
from sentientresearchagent.error_handler import get_error_handler, set_error_handler, ErrorHandler
from sentientresearchagent.exceptions import SentientError, handle_exception

# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# --- Create Flask App ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
CORS(app, origins=["http://localhost:3000"], methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], allow_headers=["Content-Type", "Authorization"], supports_credentials=True)

# Initialize SocketIO with better error handling
socketio = SocketIO(
    app, 
    cors_allowed_origins="http://localhost:3000", 
    async_mode='threading',
    logger=True,
    engineio_logger=True
)

# NEW: Initialize all systems with proper integration
def initialize_sentient_systems():
    """Initialize all Sentient systems with proper integration."""
    try:
        print("🔧 Initializing Sentient Research Agent systems...")
        
        # 1. Load configuration
        print("📋 Loading configuration...")
        config = auto_load_config()
        
        # Validate configuration
        validation = validate_config(config)
        if not validation["valid"]:
            print("⚠️  Configuration issues found:")
            for issue in validation["issues"]:
                print(f"   - {issue}")
        
        if validation["warnings"]:
            print("⚠️  Configuration warnings:")
            for warning in validation["warnings"]:
                print(f"   - {warning}")
        
        # 2. Setup logging from config
        config.setup_logging()
        
        # 3. Initialize error handling
        print("🛡️  Setting up error handling...")
        error_handler = ErrorHandler(enable_detailed_logging=True)
        set_error_handler(error_handler)
        
        # 4. Initialize cache manager
        print("💾 Setting up cache system...")
        cache_manager = init_cache_manager(config.cache)
        
        # 🔥 ADD THIS: Initialize your existing agent system
        print("🤖 Initializing agent registry...")
        from sentientresearchagent.hierarchical_agent_framework import agents
        from sentientresearchagent.hierarchical_agent_framework.agents.registry import AGENT_REGISTRY, NAMED_AGENTS
        print(f"✅ Agent registry loaded: {len(AGENT_REGISTRY)} adapters, {len(NAMED_AGENTS)} named agents")
        
        # 5. Initialize core components with new systems
        print("🧠 Initializing core components...")
        live_task_graph = TaskGraph()
        live_knowledge_store = KnowledgeStore()
        live_state_manager = StateManager(live_task_graph)
        
        # Use new configuration system for node processor
        node_processor_config = NodeProcessorConfig()
        live_hitl_coordinator = HITLCoordinator(config=node_processor_config)
        live_node_processor = NodeProcessor(
            task_graph=live_task_graph,
            knowledge_store=live_knowledge_store,
            config=config,  # NEW: Pass main config
            node_processor_config=node_processor_config  # Keep old config for compatibility
        )
        live_execution_engine = ExecutionEngine(
            task_graph=live_task_graph,
            state_manager=live_state_manager,
            knowledge_store=live_knowledge_store,
            hitl_coordinator=live_hitl_coordinator,
            config=config,  # NEW: Pass main config
            node_processor=live_node_processor
        )
        
        print("✅ All Sentient systems initialized successfully!")
        
        # Print system info
        cache_stats = cache_manager.get_stats()
        print(f"📊 Cache: {config.cache.cache_type} backend, {cache_stats['current_size']} items")
        print(f"⚙️  Execution: max {config.execution.max_concurrent_nodes} concurrent nodes")
        print(f"🔗 LLM: {config.llm.provider}/{config.llm.model}")
        
        return {
            'config': config,
            'task_graph': live_task_graph,
            'knowledge_store': live_knowledge_store,
            'state_manager': live_state_manager,
            'hitl_coordinator': live_hitl_coordinator,
            'node_processor': live_node_processor,
            'execution_engine': live_execution_engine,
            'cache_manager': cache_manager,
            'error_handler': error_handler
        }
        
    except Exception as e:
        print(f"❌ System initialization error: {e}")
        traceback.print_exc()
        
        # Try to handle with error system if available
        try:
            handled_error = handle_exception(e, context={"component": "system_initialization"})
            print(f"📋 Error details: {handled_error.to_dict()}")
        except:
            pass  # Error system not available yet
        
        sys.exit(1)

# Initialize all systems
systems = initialize_sentient_systems()

# Extract components for global use (for compatibility)
live_task_graph = systems['task_graph']
live_knowledge_store = systems['knowledge_store']
live_state_manager = systems['state_manager']
live_hitl_coordinator = systems['hitl_coordinator']
live_node_processor = systems['node_processor']
live_execution_engine = systems['execution_engine']
sentient_config = systems['config']

# --- Helper Functions ---
def broadcast_graph_update():
    """Send current graph state to all connected clients"""
    try:
        print("📡 Starting broadcast...")
        data = live_task_graph.to_visualization_dict()
        node_count = len(data.get('all_nodes', {}))
        print(f"📡 Broadcasting update: {node_count} nodes")
        socketio.emit('task_graph_update', data)
        print("📡 Broadcast completed successfully")
        return True
    except Exception as e:
        # Use new error handling
        error_handler = get_error_handler()
        if error_handler:
            error_handler.handle_error(e, component="broadcast", reraise=False)
        else:
            print(f"❌ Broadcast error: {e}")
            traceback.print_exc()
        return False

# --- WebSocket Events ---
@socketio.on('connect')
def handle_connect():
    print('👋 Client connected')
    try:
        broadcast_graph_update()
    except Exception as e:
        error_handler = get_error_handler()
        if error_handler:
            error_handler.handle_error(e, component="websocket_connect", reraise=False)
        else:
            print(f"❌ Error in connect handler: {e}")
            traceback.print_exc()

@socketio.on('disconnect')
def handle_disconnect():
    print('👋 Client disconnected')

@socketio.on('start_project')
def handle_start_project(data):
    print(f"🚀 Received start_project: {data}")
    try:
        project_goal = data.get('project_goal')
        max_steps = data.get('max_steps', sentient_config.execution.max_execution_steps)  # NEW: Use config default
        
        if not project_goal:
            emit('error', {'message': 'project_goal not provided'})
            return
        
        print(f"🚀 Starting project: {project_goal}")
        
        # Start in background thread
        thread = threading.Thread(target=run_project_in_thread, args=(project_goal, max_steps))
        thread.daemon = True 
        thread.start()
        
        emit('project_started', {'message': f"Project started: {project_goal}"})
        print("✅ Project started response sent")
        
    except Exception as e:
        error_handler = get_error_handler()
        if error_handler:
            error_handler.handle_error(e, component="start_project", reraise=False)
        else:
            print(f"❌ Error in start_project handler: {e}")
            traceback.print_exc()
        emit('error', {'message': f'Server error: {str(e)}'})

# Add a catch-all error handler
@socketio.on_error_default
def default_error_handler(e):
    error_handler = get_error_handler()
    if error_handler:
        error_handler.handle_error(e, component="socketio", reraise=False)
    else:
        print(f"❌ SocketIO error: {e}")
        traceback.print_exc()

# --- Project Execution ---
async def run_project_cycle_async(goal, max_steps):
    """Run the project cycle with new error handling"""
    print(f"🎯 Initializing project: {goal}")
    
    try:
        # Clear previous state
        print("🧹 Clearing previous state...")
        live_task_graph.nodes.clear()
        live_task_graph.graphs.clear()
        live_task_graph.root_graph_id = None
        live_task_graph.overall_project_goal = None
        
        # Clear cache if configured to do so
        cache_manager = systems['cache_manager']
        if cache_manager and sentient_config.cache.enabled:
            # Optionally clear old project cache
            cache_manager.clear_namespace("project_execution")
        
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
        
        # Run execution cycle (max_steps now comes from config by default)
        print("⚡ Starting execution...")
        await live_execution_engine.run_cycle(max_steps=max_steps)
        
        # Final update and stats
        broadcast_graph_update()
        
        # Show final statistics
        if cache_manager:
            cache_stats = cache_manager.get_stats()
            print(f"💾 Cache stats: {cache_stats['hits']} hits, {cache_stats['hit_rate_percent']}% hit rate")
        
        error_handler = get_error_handler()
        if error_handler:
            error_stats = error_handler.get_error_stats()
            print(f"🛡️  Error stats: {error_stats['total_errors']} total errors")
        
        print("✅ Project completed")
        
    except Exception as e:
        error_handler = get_error_handler()
        if error_handler:
            error_handler.handle_error(e, component="project_execution", reraise=False)
        else:
            print(f"❌ Project error: {e}")
            traceback.print_exc()
        
        try:
            broadcast_graph_update()
        except:
            print("❌ Failed to broadcast error state")

def run_project_in_thread(goal, max_steps):
    """Thread wrapper for async execution"""
    print(f"🧵 Thread started for: {goal}")
    try:
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_project_cycle_async(goal, max_steps))
    except Exception as e:
        error_handler = get_error_handler()
        if error_handler:
            error_handler.handle_error(e, component="project_thread", reraise=False)
        else:
            print(f"❌ Thread error: {e}")
            traceback.print_exc()
    finally:
        print(f"🏁 Thread finished for: {goal}")

# --- HTTP Endpoints ---
@app.route('/api/task-graph', methods=['GET'])
def get_task_graph_data():
    """Get current graph data"""
    try:
        data = live_task_graph.to_visualization_dict()
        response = make_response(jsonify(data))
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:3000'
        return response
    except Exception as e:
        error_handler = get_error_handler()
        if error_handler:
            error_handler.handle_error(e, component="http_task_graph", reraise=False)
        else:
            print(f"❌ HTTP endpoint error: {e}")
            traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/start-project', methods=['POST'])
def start_project():
    """HTTP endpoint to start project"""
    try:
        data = request.get_json()
        if not data or 'project_goal' not in data:
            return jsonify({"error": "project_goal not provided"}), 400
        
        project_goal = data['project_goal']
        max_steps = data.get('max_steps', sentient_config.execution.max_execution_steps)
        
        thread = threading.Thread(target=run_project_in_thread, args=(project_goal, max_steps))
        thread.daemon = True 
        thread.start()
        
        return jsonify({"message": f"Project '{project_goal}' initiated"}), 202
    except Exception as e:
        error_handler = get_error_handler()
        if error_handler:
            error_handler.handle_error(e, component="http_start_project", reraise=False)
        else:
            print(f"❌ HTTP start project error: {e}")
            traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# NEW: Add system info endpoint
@app.route('/api/system-info', methods=['GET'])
def get_system_info():
    """Get system information and statistics"""
    try:
        cache_manager = systems['cache_manager']
        error_handler = get_error_handler()
        
        info = {
            "config": {
                "llm_provider": sentient_config.llm.provider,
                "llm_model": sentient_config.llm.model,
                "cache_enabled": sentient_config.cache.enabled,
                "cache_type": sentient_config.cache.cache_type,
                "max_concurrent_nodes": sentient_config.execution.max_concurrent_nodes,
                "environment": sentient_config.environment
            },
            "cache_stats": cache_manager.get_stats() if cache_manager else None,
            "error_stats": error_handler.get_error_stats() if error_handler else None,
            "graph_stats": {
                "total_nodes": len(live_task_graph.nodes),
                "total_graphs": len(live_task_graph.graphs)
            }
        }
        
        return jsonify(info)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Main Entry Point ---
if __name__ == '__main__':
    print("🚀 Starting Sentient Research Agent Server...")
    print("📡 WebSocket: http://localhost:5000")
    print("🌐 Frontend: http://localhost:3000")
    print("📊 System Info: http://localhost:5000/api/system-info")
    
    try:
        socketio.run(app, debug=False, host='0.0.0.0', port=5000, use_reloader=False)
    except Exception as e:
        error_handler = get_error_handler()
        if error_handler:
            error_handler.handle_error(e, component="server_startup", reraise=False)
        else:
            print(f"❌ Server startup error: {e}")
            traceback.print_exc()