import argparse
import multiprocessing
import pandas as pd
import time
import traceback
from tqdm import tqdm
from threading import Lock
import queue
import os
import requests
import json
from datetime import datetime
import socketio as socketio_client
from typing import Dict, Any, Optional

result_lock = Lock()

class ServerEvaluationClient:
    """Client for communicating with the Sentient Research Agent server."""
    
    def __init__(self, server_url: str = "http://localhost:5000"):
        self.server_url = server_url
        self.session = requests.Session()
        self.sio = None
        self._connected = False
        
    def connect_websocket(self):
        """Connect to the server via WebSocket for real-time updates."""
        try:
            self.sio = socketio_client.Client()
            
            @self.sio.on('connect')
            def on_connect():
                print(f"✅ WebSocket connected to {self.server_url}")
                self._connected = True
                
            @self.sio.on('disconnect')
            def on_disconnect():
                print(f"❌ WebSocket disconnected from {self.server_url}")
                self._connected = False
                
            self.sio.connect(self.server_url)
            # Wait for connection
            timeout = 5
            start = time.time()
            while not self._connected and (time.time() - start) < timeout:
                time.sleep(0.1)
                
        except Exception as e:
            print(f"⚠️ Failed to connect WebSocket: {e}")
            
    def disconnect_websocket(self):
        """Disconnect WebSocket."""
        if self.sio:
            self.sio.disconnect()
            
    def create_configured_project(self, goal: str, config: Dict[str, Any], max_steps: int = 250) -> Optional[Dict[str, Any]]:
        """Create a project with custom configuration."""
        try:
            response = self.session.post(
                f"{self.server_url}/api/projects/configured",
                json={
                    "goal": goal,
                    "config": config,
                    "max_steps": max_steps
                }
            )
            if response.status_code == 201:
                return response.json()
            else:
                print(f"❌ Failed to create project: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"❌ Error creating project: {e}")
            return None
            
    def wait_for_project_completion(self, project_id: str, timeout: int = 1800) -> Dict[str, Any]:
        """Wait for a project to complete and return its final state."""
        start_time = time.time()
        last_status = None
        
        while (time.time() - start_time) < timeout:
            try:
                # Get project status
                response = self.session.get(f"{self.server_url}/api/projects/{project_id}")
                if response.status_code == 200:
                    project_data = response.json()
                    project = project_data.get('project', {})
                    status = project.get('status', 'unknown')
                    
                    if status != last_status:
                        print(f"📊 Project {project_id} status: {status}")
                        last_status = status
                    
                    if status in ['completed', 'failed']:
                        # Get the final project state with results
                        return self.get_project_results(project_id)
                        
                time.sleep(2)  # Poll every 2 seconds
                
            except Exception as e:
                print(f"⚠️ Error checking project status: {e}")
                time.sleep(5)
                
        # Timeout reached
        print(f"⏱️ Project {project_id} timed out after {timeout} seconds")
        return self.get_project_results(project_id)
        
    def get_project_results(self, project_id: str) -> Dict[str, Any]:
        """Get the complete results for a project."""
        try:
            # Try to get saved results first
            response = self.session.get(f"{self.server_url}/api/projects/{project_id}/load-results")
            if response.status_code == 200:
                return response.json()
                
            # Fallback to getting project state
            response = self.session.get(f"{self.server_url}/api/projects/{project_id}")
            if response.status_code == 200:
                return response.json()
                
            return {"error": "Failed to get project results"}
            
        except Exception as e:
            print(f"❌ Error getting project results: {e}")
            return {"error": str(e)}


def save_checkpoint(results, df, output_file, lock):
    """Save checkpoint with project IDs for frontend reference."""
    try:
        sorted_results = sorted(results, key=lambda x: x['index'])
        results_df = pd.DataFrame(sorted_results)
        
        # Copy original DataFrame
        output_df = df.copy()
        
        # Add all result columns
        for col in results_df.columns:
            if col != 'index':
                output_df.loc[results_df['index'], col] = results_df[col].values
                
        output_df.to_csv(output_file, index=False)
        print(f"💾 [Checkpoint] Saved {len(results)} results -> {output_file}")
        
    except Exception as e:
        print(f"⚠️ Failed to save checkpoint: {e}")


def evaluation_worker(task_queue: multiprocessing.Queue, result_queue: multiprocessing.Queue, 
                     worker_config: dict):
    """Worker that creates projects via the server API."""
    process_name = multiprocessing.current_process().name
    
    # Create a client for this worker
    client = ServerEvaluationClient(worker_config['server_url'])
    
    # Optionally connect WebSocket for monitoring (not required for basic operation)
    if worker_config.get('enable_websocket', False):
        client.connect_websocket()
    
    print(f"🤖 [{process_name}] Worker initialized, connected to {worker_config['server_url']}")
    
    while True:
        try:
            task = task_queue.get(timeout=1)
            if task is None:
                # Sentinel value - put it back for other workers
                task_queue.put(None)
                break
        except queue.Empty:
            continue
            
        query, idx = task
        
        try:
            print(f"🚀 [{process_name}] Creating project for query #{idx+1}: '{query}'")
            start_time = time.time()
            
            # Add delay to avoid rate limiting
            if worker_config.get('request_delay', 0) > 0:
                delay = worker_config['request_delay']
                print(f"⏱️ [{process_name}] Waiting {delay}s before request (rate limiting)")
                time.sleep(delay)
            
            # Create the project with configuration
            project_response = client.create_configured_project(
                goal=query,
                config=worker_config['agent_config'],
                max_steps=worker_config['max_steps']
            )
            
            if not project_response:
                result_queue.put({
                    'query': query,
                    'result': 'Error: Failed to create project',
                    'index': idx,
                    'error': True
                })
                continue
                
            project_id = project_response['project']['id']
            print(f"✅ [{process_name}] Created project {project_id} for query #{idx+1}")
            
            # Wait for completion
            final_results = client.wait_for_project_completion(
                project_id, 
                timeout=worker_config.get('execution_timeout', 1800)
            )
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            # Extract the final output
            final_output = "No output generated"
            
            # Try different paths to find the result
            if 'basic_state' in final_results:
                graph_data = final_results.get('basic_state', {})
            elif 'graph_data' in final_results:
                graph_data = final_results.get('graph_data', {})
            elif 'state' in final_results:
                graph_data = final_results.get('state', {})
            else:
                graph_data = final_results
                
            # Find root node result with more robust error handling
            all_nodes = graph_data.get('all_nodes', {})
            for node_key, node in all_nodes.items():
                try:
                    # FIX: More robust handling of different node types
                    if isinstance(node, str):
                        try:
                            node = json.loads(node)
                        except (json.JSONDecodeError, TypeError):
                            print(f"⚠️ Skipping invalid JSON node: {node_key}")
                            continue
                    
                    if not isinstance(node, dict):
                        print(f"⚠️ Skipping non-dict node: {node_key} (type: {type(node)})")
                        continue
                    
                    # Safe access with .get() method
                    layer = node.get('layer')
                    parent_node_id = node.get('parent_node_id')
                    
                    if layer == 0 and not parent_node_id:
                        # This is the root node - extract result safely
                        full_result = node.get('full_result', {})
                        
                        # Ensure full_result is a dict
                        if not isinstance(full_result, dict):
                            full_result = {}
                        
                        if full_result.get('output_text_with_citations'):
                            final_output = full_result['output_text_with_citations']
                        elif full_result.get('output_text'):
                            final_output = full_result['output_text']
                        elif node.get('output_summary'):
                            final_output = node['output_summary']
                        break
                        
                except Exception as e:
                    print(f"⚠️ Error processing node {node_key}: {e}")
                    continue
                
            print(f"✅ [{process_name}] Completed query #{idx+1} in {execution_time:.2f}s")
            
            result_queue.put({
                'query': query,
                'result': final_output,
                'index': idx,
                'project_id': project_id,  # Store project ID for frontend reference
                'execution_time': execution_time,
                'node_count': len(all_nodes),
                'completion_status': final_results.get('metadata', {}).get('completion_status', 'unknown')
            })
            
        except Exception as e:
            print(f"❌ [{process_name}] Error on query #{idx+1}: {e}")
            traceback.print_exc()
            result_queue.put({
                'query': query,
                'result': f"Error: {str(e)}",
                'index': idx,
                'error': True
            })
            
    # Cleanup
    if worker_config.get('enable_websocket', False):
        client.disconnect_websocket()
    print(f"🏁 [{process_name}] Worker finished")


def main():
    parser = argparse.ArgumentParser(description="Run evaluations through the Sentient Agent Server")
    parser.add_argument("--input-file", type=str, default="datasets/seal-0.csv", 
                       help="Path to the input CSV/parquet file with queries")
    parser.add_argument("--output-file", default="server_eval_results.csv", type=str, 
                       help="Path to save the results CSV file")
    parser.add_argument("--query-column", type=str, default="question", 
                       help="Name of the column containing queries")
    parser.add_argument("--num-examples", type=int, default=None, 
                       help="Number of examples to run")
    parser.add_argument("--checkpoint-interval", type=int, default=10, 
                       help="Number of queries between checkpoints")
    parser.add_argument("--checkpoint-file", type=str, default="server_checkpoint.csv", 
                       help="Path to save checkpoint file")
    
    # Server settings
    parser.add_argument("--server-url", type=str, default="http://localhost:5000", 
                       help="URL of the Sentient Agent server")
    parser.add_argument("--enable-websocket", action='store_true', 
                       help="Enable WebSocket monitoring")
    
    # Agent configuration
    parser.add_argument("--profile-name", type=str, default="general_agent", 
                       help="Agent profile name")
    parser.add_argument("--enable-hitl", action='store_true', 
                       help="Enable HITL (Human-in-the-loop)")
    parser.add_argument("--max-concurrent-tasks", type=int, default=10, 
                       help="Maximum concurrent tasks")
    parser.add_argument("--max-planning-depth", type=int, default=3, 
                       help="Maximum planning depth")
    parser.add_argument("--max-steps", type=int, default=250, 
                       help="Maximum execution steps per query")
    parser.add_argument("--execution-timeout", type=int, default=1800, 
                       help="Timeout for each execution in seconds")
    
    # Rate limiting settings
    parser.add_argument("--request-delay", type=float, default=5.0, 
                       help="Delay between requests in seconds (to avoid rate limiting)")
    parser.add_argument("--worker-startup-delay", type=float, default=2.0, 
                       help="Delay between worker startup in seconds")
    
    # Multiprocessing settings
    parser.add_argument("--num-processes", type=int, default=min(2, multiprocessing.cpu_count()), 
                       help="Number of parallel processes (default: 2 to avoid rate limiting)")
    
    args = parser.parse_args()
    
    # Test server connection
    print(f"🔍 Testing connection to server at {args.server_url}...")
    try:
        response = requests.get(f"{args.server_url}/api/system-info")
        if response.status_code == 200:
            system_info = response.json()
            print(f"✅ Connected to server - Profile: {system_info.get('current_profile')}")
        else:
            print(f"❌ Server returned status {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Failed to connect to server: {e}")
        print("Make sure the server is running with: python -m sentientresearchagent.server")
        return
    
    # Load dataset
    try:
        df = pd.read_csv(args.input_file)
        if args.num_examples:
            df = df.iloc[:args.num_examples]
        if args.query_column not in df.columns:
            print(f"Error: Query column '{args.query_column}' not found")
            return
        queries = df[args.query_column].tolist()
    except Exception as e:
        print(f"Error reading input file: {e}")
        return
    
    # Prepare worker configuration
    worker_config = {
        'server_url': args.server_url,
        'enable_websocket': args.enable_websocket,
        'max_steps': args.max_steps,
        'execution_timeout': args.execution_timeout,
        'request_delay': args.request_delay,
        'agent_config': {
            'llm': {
                'provider': 'openai',
                'model': 'gpt-4o',
                'temperature': 0.7
            },
            'execution': {
                'enable_hitl': args.enable_hitl,
                'hitl_root_plan_only': True,
                'max_concurrent_nodes': min(2, args.max_concurrent_tasks),  # Limit concurrent nodes for rate limiting
                'max_recursion_depth': args.max_planning_depth,
                'max_execution_steps': args.max_steps,
                'rate_limit_rpm': 20,  # Conservative rate limit for evaluations
                'hitl_timeout_seconds': 300,
                'hitl_after_plan_generation': False,
                'hitl_after_modified_plan': False,
                'hitl_after_atomizer': False,
                'hitl_before_execute': False
            },
            'cache': {
                'enabled': True,
                'ttl_seconds': 3600,
                'max_size': 1000,
                'cache_type': 'file'
            }
        }
    }
    
    # Create queues
    task_queue = multiprocessing.Queue()
    result_queue = multiprocessing.Queue()
    
    # Enqueue all tasks
    for i, query in enumerate(queries):
        task_queue.put((query, i))
    
    # Add sentinel values
    for _ in range(args.num_processes):
        task_queue.put(None)
    
    # Start worker processes with staggered startup
    processes = []
    print(f"🏁 Starting {args.num_processes} worker processes for {len(queries)} queries...")
    for i in range(args.num_processes):
        process = multiprocessing.Process(
            target=evaluation_worker,
            args=(task_queue, result_queue, worker_config),
            name=f"EvalWorker-{i+1}"
        )
        processes.append(process)
        process.start()
        
        # Add delay between worker startup to avoid initial rate limiting burst
        if i < args.num_processes - 1 and args.worker_startup_delay > 0:
            print(f"⏱️ Waiting {args.worker_startup_delay}s before starting next worker...")
            time.sleep(args.worker_startup_delay)
    
    # Collect results
    results = []
    num_queries = len(queries)
    
    # Add timestamp for tracking
    eval_start_time = datetime.now()
    
    with tqdm(total=num_queries, desc="Processing queries", ncols=100) as pbar:
        while len(results) < num_queries:
            try:
                result = result_queue.get(timeout=300)
                with result_lock:
                    results.append(result)
                    pbar.update(1)
                    
                    # Show project ID for frontend reference
                    if 'project_id' in result:
                        print(f"📊 Progress: {len(results)}/{num_queries} - "
                              f"Latest project: {result['project_id']}")
                    
                    if len(results) % args.checkpoint_interval == 0:
                        save_checkpoint(results, df, args.checkpoint_file, result_lock)
                        
            except queue.Empty:
                print("⏱️ Timeout waiting for results. Checking worker status...")
                if not any(p.is_alive() for p in processes):
                    print("❌ All workers terminated unexpectedly")
                    break
    
    # Wait for all processes
    for process in processes:
        process.join()
    
    print("\n✅ All evaluations completed")
    
    # Save final results
    if results:
        results.sort(key=lambda x: x['index'])
        results_df = pd.DataFrame(results)
        
        output_df = df.copy()
        for col in results_df.columns:
            if col != 'index':
                output_df[col] = results_df[col].values
        
        # Add evaluation metadata
        output_df['eval_timestamp'] = eval_start_time.isoformat()
        output_df['server_url'] = args.server_url
        
        output_df.to_csv(args.output_file, index=False)
        print(f"💾 Results saved to {args.output_file}")
        
        # Print summary
        print("\n📊 Evaluation Summary:")
        print(f"  Total queries: {len(results)}")
        print(f"  Successful: {sum(1 for r in results if not r.get('error', False))}")
        print(f"  Failed: {sum(1 for r in results if r.get('error', False))}")
        if any('execution_time' in r for r in results):
            avg_time = sum(r.get('execution_time', 0) for r in results) / len(results)
            print(f"  Average execution time: {avg_time:.2f} seconds")
        
        # Print project IDs for frontend reference
        print("\n🌐 Projects created (viewable in frontend):")
        for i, result in enumerate(results[:5]):  # Show first 5
            if 'project_id' in result:
                print(f"  - {result['project_id']}: {result['query'][:50]}...")
        if len(results) > 5:
            print(f"  ... and {len(results) - 5} more")
            
    else:
        print("No results were generated")


if __name__ == "__main__":
    try:
        multiprocessing.set_start_method("spawn", force=True)
    except RuntimeError:
        pass
    main() 