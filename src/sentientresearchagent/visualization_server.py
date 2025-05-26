from flask import Flask, jsonify, request, make_response, send_file
from flask_cors import CORS 
from flask_socketio import SocketIO, emit
import threading 
import asyncio 
import time
import traceback
import sys
from agno.exceptions import StopAgentRun 
from typing import Dict, Any

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

# NEW: Import project manager
from sentientresearchagent.project_manager import ProjectManager

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

# NEW: Initialize project manager
project_manager = ProjectManager()

# Store project-specific task graphs
project_graphs: Dict[str, Any] = {}
project_execution_engines: Dict[str, Any] = {}

def sync_project_to_display(project_id: str):
    """Sync a project's current state to the display graph and broadcast"""
    try:
        if project_id not in project_graphs:
            return False
            
        project_task_graph = project_graphs[project_id]['task_graph']
        
        # Copy project state to live display graph
        live_task_graph.nodes.clear()
        live_task_graph.nodes.update(project_task_graph.nodes)
        live_task_graph.graphs.clear()
        live_task_graph.graphs.update(project_task_graph.graphs)
        live_task_graph.overall_project_goal = project_task_graph.overall_project_goal
        live_task_graph.root_graph_id = project_task_graph.root_graph_id
        
        # Broadcast the update
        broadcast_graph_update()
        return True
        
    except Exception as e:
        print(f"❌ Failed to sync project {project_id} to display: {e}")
        return False

def create_project_update_callback(project_id: str):
    """Create a callback function that syncs project updates to display"""
    def update_callback():
        # Only sync if this is the current project
        current_project = project_manager.get_current_project()
        if current_project and current_project.id == project_id:
            sync_project_to_display(project_id)
    
    return update_callback

def get_or_create_project_graph(project_id: str):
    """Get or create a project-specific task graph and execution engine"""
    if project_id not in project_graphs:
        # Create new instances for this project
        from sentientresearchagent.hierarchical_agent_framework.graph.task_graph import TaskGraph
        from sentientresearchagent.hierarchical_agent_framework.graph.state_manager import StateManager
        from sentientresearchagent.hierarchical_agent_framework.graph.execution_engine import ExecutionEngine
        from sentientresearchagent.hierarchical_agent_framework.node.node_processor import NodeProcessor
        from sentientresearchagent.hierarchical_agent_framework.node.node_configs import NodeProcessorConfig
        from sentientresearchagent.hierarchical_agent_framework.node.hitl_coordinator import HITLCoordinator
        
        # Create project-specific components
        project_task_graph = TaskGraph()
        project_state_manager = StateManager(project_task_graph)
        project_hitl_coordinator = HITLCoordinator(config=NodeProcessorConfig())
        
        # Create update callback for real-time sync
        update_callback = create_project_update_callback(project_id)
        
        project_node_processor = NodeProcessor(
            task_graph=project_task_graph,
            knowledge_store=live_knowledge_store,
            config=sentient_config,
            node_processor_config=NodeProcessorConfig()
        )
        
        project_execution_engine = ExecutionEngine(
            task_graph=project_task_graph,
            state_manager=project_state_manager,
            knowledge_store=live_knowledge_store,
            hitl_coordinator=project_hitl_coordinator,
            config=sentient_config,
            node_processor=project_node_processor
        )
        
        # Store the project-specific components
        project_graphs[project_id] = {
            'task_graph': project_task_graph,
            'state_manager': project_state_manager,
            'execution_engine': project_execution_engine,
            'node_processor': project_node_processor,
            'hitl_coordinator': project_hitl_coordinator,
            'update_callback': update_callback
        }
        
        print(f"✅ Created new execution environment for project {project_id}")
    
    return project_graphs[project_id]

# Create a custom execution engine wrapper that provides real-time updates
class RealtimeExecutionWrapper:
    def __init__(self, project_id: str, execution_engine, update_callback):
        self.project_id = project_id
        self.execution_engine = execution_engine
        self.update_callback = update_callback
        
    async def initialize_project(self, root_goal: str):
        """Initialize project with real-time updates"""
        result = self.execution_engine.initialize_project(root_goal=root_goal)
        # Trigger update after initialization
        self.update_callback()
        return result
    
    async def run_cycle(self, max_steps: int = 250):
        """Run execution cycle with periodic real-time updates"""
        import asyncio
        
        # Create a task for the execution
        async def execute_with_updates():
            # Start the execution cycle
            execution_task = asyncio.create_task(
                self.execution_engine.run_cycle(max_steps=max_steps)
            )
            
            # Create a periodic update task
            async def periodic_updates():
                while not execution_task.done():
                    await asyncio.sleep(2)  # Update every 2 seconds
                    if not execution_task.done():
                        self.update_callback()
            
            update_task = asyncio.create_task(periodic_updates())
            
            try:
                # Wait for execution to complete
                result = await execution_task
                # Cancel the update task
                update_task.cancel()
                # Final update
                self.update_callback()
                return result
            except Exception as e:
                update_task.cancel()
                # Update on error too
                self.update_callback()
                raise e
        
        return await execute_with_updates()

def load_project_into_graph(project_id: str) -> bool:
    """Load a project's state into the live task graph for display"""
    try:
        # Get or create project-specific graph
        project_components = get_or_create_project_graph(project_id)
        project_task_graph = project_components['task_graph']
        
        # Load saved state into the project's task graph
        project_state = project_manager.load_project_state(project_id)
        project = project_manager.get_project(project_id)
        
        if project_state:
            # Clear and reload the project's task graph
            project_task_graph.nodes.clear()
            project_task_graph.graphs.clear()
            project_task_graph.root_graph_id = None
            project_task_graph.overall_project_goal = None
            
            if 'all_nodes' in project_state:
                # Load nodes as dictionaries (they're already serialized)
                for node_id, node_data in project_state['all_nodes'].items():
                    project_task_graph.nodes[node_id] = node_data
            
            if 'graphs' in project_state:
                project_task_graph.graphs.update(project_state['graphs'])
            
            if 'overall_project_goal' in project_state:
                project_task_graph.overall_project_goal = project_state['overall_project_goal']
            elif project:
                project_task_graph.overall_project_goal = project.goal
                
            if 'root_graph_id' in project_state:
                project_task_graph.root_graph_id = project_state['root_graph_id']
        
        elif project:
            # No saved state, just set the goal
            project_task_graph.overall_project_goal = project.goal
        
        # Sync to display
        sync_project_to_display(project_id)
        
        print(f"✅ Loaded project {project_id} into display graph: {len(live_task_graph.nodes)} nodes")
        return True
        
    except Exception as e:
        print(f"❌ Failed to load project {project_id}: {e}")
        traceback.print_exc()
        return False

def save_current_project_state():
    """Save the current live graph state to the current project"""
    current_project = project_manager.get_current_project()
    if current_project:
        try:
            data = live_task_graph.to_visualization_dict()
            project_manager.save_project_state(current_project.id, data)
            
            # Also update the project-specific graph if it exists
            if current_project.id in project_graphs:
                project_task_graph = project_graphs[current_project.id]['task_graph']
                project_task_graph.nodes.clear()
                project_task_graph.nodes.update(live_task_graph.nodes)
                project_task_graph.graphs.clear()
                project_task_graph.graphs.update(live_task_graph.graphs)
                project_task_graph.overall_project_goal = live_task_graph.overall_project_goal
                project_task_graph.root_graph_id = live_task_graph.root_graph_id
            
            print(f"💾 Saved state for project {current_project.id}")
        except Exception as e:
            print(f"❌ Failed to save current project state: {e}")

def broadcast_graph_update():
    """Send current graph state to all connected clients with project info"""
    try:
        print("📡 Starting broadcast...")
        
        # Get the current state
        if hasattr(live_task_graph, 'to_visualization_dict'):
            data = live_task_graph.to_visualization_dict()
        else:
            data = {
                'all_nodes': getattr(live_task_graph, 'nodes', {}),
                'graphs': getattr(live_task_graph, 'graphs', {}),
                'overall_project_goal': getattr(live_task_graph, 'overall_project_goal', None),
                'root_graph_id': getattr(live_task_graph, 'root_graph_id', None)
            }
        
        # Add current project info
        current_project = project_manager.get_current_project()
        if current_project:
            data['current_project'] = current_project.to_dict()
        
        node_count = len(data.get('all_nodes', {}))
        print(f"📡 Broadcasting update: {node_count} nodes")
        socketio.emit('task_graph_update', data)
        
        # Save state for current project (but don't create infinite loop)
        if current_project:
            try:
                project_manager.save_project_state(current_project.id, data)
            except Exception as e:
                print(f"⚠️ Failed to save during broadcast: {e}")
        
        print("📡 Broadcast completed successfully")
        return True
    except Exception as e:
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
        max_steps = data.get('max_steps', sentient_config.execution.max_execution_steps)
        project_id = data.get('project_id')  # NEW: Optional project ID
        
        if not project_goal:
            emit('error', {'message': 'project_goal not provided'})
            return
        
        # Create or use existing project
        if project_id:
            project = project_manager.get_project(project_id)
            if not project:
                emit('error', {'message': 'Project not found'})
                return
        else:
            project = project_manager.create_project(project_goal, max_steps)
            project_id = project.id
        
        print(f"🚀 Starting project: {project_id} - {project_goal}")
        
        # Start in background thread
        thread = threading.Thread(
            target=run_project_in_thread, 
            args=(project_id, project_goal, max_steps)
        )
        thread.daemon = True 
        thread.start()
        
        emit('project_started', {
            'message': f"Project started: {project_goal}",
            'project': project.to_dict()
        })
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
async def run_project_cycle_async(project_id: str, goal: str, max_steps: int):
    """Run the project cycle with proper project isolation and real-time updates"""
    print(f"🎯 Initializing project: {project_id} - {goal}")
    
    try:
        # Get or create project-specific components
        project_components = get_or_create_project_graph(project_id)
        project_task_graph = project_components['task_graph']
        project_execution_engine = project_components['execution_engine']
        update_callback = project_components['update_callback']
        
        # Create real-time wrapper
        realtime_engine = RealtimeExecutionWrapper(
            project_id, 
            project_execution_engine, 
            update_callback
        )
        
        # Set as current project
        project_manager.set_current_project(project_id)
        
        # Load existing state into project graph
        project_state = project_manager.load_project_state(project_id)
        if project_state and 'all_nodes' in project_state and len(project_state['all_nodes']) > 0:
            print(f"📊 Resuming project with {len(project_state['all_nodes'])} existing nodes")
            
            # Load state into project graph
            project_task_graph.nodes.clear()
            for node_id, node_data in project_state['all_nodes'].items():
                project_task_graph.nodes[node_id] = node_data
            
            if 'graphs' in project_state:
                project_task_graph.graphs.update(project_state['graphs'])
            if 'overall_project_goal' in project_state:
                project_task_graph.overall_project_goal = project_state['overall_project_goal']
            if 'root_graph_id' in project_state:
                project_task_graph.root_graph_id = project_state['root_graph_id']
            
            # Update project status
            project_manager.update_project(project_id, status='running')
            
            # Sync to display and broadcast
            sync_project_to_display(project_id)
            
            # Continue execution from where it left off
            await realtime_engine.run_cycle(max_steps=max_steps)
        else:
            print("🧹 Starting fresh project...")
            
            # Clear project graph (but not other projects!)
            project_task_graph.nodes.clear()
            project_task_graph.graphs.clear()
            project_task_graph.root_graph_id = None
            project_task_graph.overall_project_goal = None
            
            # Clear project-specific cache
            cache_manager = systems['cache_manager']
            if cache_manager and sentient_config.cache.enabled:
                cache_manager.clear_namespace(f"project_{project_id}")
            
            # Initialize project using project-specific execution engine with real-time updates
            print("🚀 Calling initialize_project...")
            start_time = time.time()
            
            await realtime_engine.initialize_project(root_goal=goal)
            
            init_time = time.time() - start_time
            print(f"⏱️ Initialization took {init_time:.2f} seconds")
            
            # Update project status
            project_manager.update_project(project_id, status='running')
            
            print(f"📊 Initial state sent: {len(project_task_graph.nodes)} nodes")
            
            # Run execution cycle using real-time wrapper
            print("⚡ Starting execution...")
            await realtime_engine.run_cycle(max_steps=max_steps)
        
        # Update project status
        project_manager.update_project(project_id, status='completed')
        
        # Final sync and broadcast
        sync_project_to_display(project_id)
        
        print("✅ Project completed")
        
    except Exception as e:
        # Update project status to failed
        project_manager.update_project(project_id, status='failed')
        
        error_handler = get_error_handler()
        if error_handler:
            error_handler.handle_error(e, component="project_execution", reraise=False)
        else:
            print(f"❌ Project error: {e}")
            traceback.print_exc()
        
        try:
            # Sync error state
            if project_id in project_graphs:
                sync_project_to_display(project_id)
        except:
            print("❌ Failed to broadcast error state")

def run_project_in_thread(project_id: str, goal: str, max_steps: int):
    """Thread wrapper for async execution with project management"""
    print(f"🧵 Thread started for project: {project_id}")
    try:
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_project_cycle_async(project_id, goal, max_steps))
    except Exception as e:
        error_handler = get_error_handler()
        if error_handler:
            error_handler.handle_error(e, component="project_thread", reraise=False)
        else:
            print(f"❌ Thread error: {e}")
            traceback.print_exc()
    finally:
        print(f"🏁 Thread finished for project: {project_id}")

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

# --- NEW: Project Management Endpoints ---
@app.route('/api/projects', methods=['GET'])
def get_projects():
    """Get all projects"""
    try:
        projects = project_manager.get_all_projects()
        return jsonify({
            "projects": [p.to_dict() for p in projects],
            "current_project_id": project_manager.current_project_id
        })
    except Exception as e:
        error_handler = get_error_handler()
        if error_handler:
            error_handler.handle_error(e, component="get_projects", reraise=False)
        return jsonify({"error": str(e)}), 500

@app.route('/api/projects', methods=['POST'])
def create_project():
    """Create a new project"""
    try:
        data = request.get_json()
        if not data or 'goal' not in data:
            return jsonify({"error": "goal is required"}), 400
        
        goal = data['goal']
        max_steps = data.get('max_steps', sentient_config.execution.max_execution_steps)
        
        # Create project
        project = project_manager.create_project(goal, max_steps)
        
        # Start project execution in background
        thread = threading.Thread(
            target=run_project_in_thread, 
            args=(project.id, goal, max_steps)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "project": project.to_dict(),
            "message": "Project created and started"
        }), 201
        
    except Exception as e:
        error_handler = get_error_handler()
        if error_handler:
            error_handler.handle_error(e, component="create_project", reraise=False)
        return jsonify({"error": str(e)}), 500

@app.route('/api/projects/<project_id>', methods=['GET'])
def get_project(project_id: str):
    """Get a specific project and its state"""
    try:
        project = project_manager.get_project(project_id)
        if not project:
            return jsonify({"error": "Project not found"}), 404
        
        # Load project state if it exists
        project_state = project_manager.load_project_state(project_id)
        
        return jsonify({
            "project": project.to_dict(),
            "state": project_state
        })
        
    except Exception as e:
        error_handler = get_error_handler()
        if error_handler:
            error_handler.handle_error(e, component="get_project", reraise=False)
        return jsonify({"error": str(e)}), 500

@app.route('/api/projects/<project_id>/switch', methods=['POST'])
def switch_project(project_id: str):
    """Switch to a different project"""
    try:
        # Save current project state if there is one
        save_current_project_state()
        
        # Switch to new project
        if not project_manager.set_current_project(project_id):
            return jsonify({"error": "Project not found"}), 404
        
        # Load new project state
        if not load_project_into_graph(project_id):
            return jsonify({"error": "Failed to load project state"}), 500
        
        # Broadcast update
        broadcast_graph_update()
        
        project = project_manager.get_project(project_id)
        return jsonify({
            "project": project.to_dict() if project else None,
            "message": f"Switched to project {project_id}"
        })
        
    except Exception as e:
        error_handler = get_error_handler()
        if error_handler:
            error_handler.handle_error(e, component="switch_project", reraise=False)
        return jsonify({"error": str(e)}), 500

@app.route('/api/projects/<project_id>', methods=['DELETE'])
def delete_project(project_id: str):
    """Delete a project"""
    try:
        if not project_manager.delete_project(project_id):
            return jsonify({"error": "Project not found"}), 404
        
        # If this was the current project, clear the graph
        if project_manager.current_project_id is None:
            live_task_graph.nodes.clear()
            live_task_graph.graphs.clear()
            live_task_graph.root_graph_id = None
            live_task_graph.overall_project_goal = None
            broadcast_graph_update()
        
        return jsonify({"message": "Project deleted successfully"})
        
    except Exception as e:
        error_handler = get_error_handler()
        if error_handler:
            error_handler.handle_error(e, component="delete_project", reraise=False)
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