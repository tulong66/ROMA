import argparse
import multiprocessing
import pandas as pd
import time
import traceback
from sentientresearchagent.framework_entry import ProfiledSentientAgent
import queue

def agent_worker(task_queue: multiprocessing.Queue, result_queue: multiprocessing.Queue, agent_settings: dict):
    """
    A worker function for a process.
    It continuously fetches queries from the task_queue, executes them,
    and puts the result in the result_queue.
    """
    process_name = multiprocessing.current_process().name
    agent = None
    try:
        # Each process creates its own agent instance. This guarantees
        # that all state, including the agent registry, is completely isolated.
        print(f"🤖 [{process_name}] Creating a dedicated agent instance...")
        agent = ProfiledSentientAgent.create_with_profile(
            profile_name=agent_settings["profile_name"],
            enable_hitl_override=agent_settings["enable_hitl_override"],
            max_concurrent_tasks=agent_settings["max_concurrent_tasks"],
            max_planning_depth=agent_settings["max_planning_depth"]
        )
        print(f"✅ [{process_name}] Agent instance created.")
    except Exception as e:
        print(f"❌ [{process_name}] Failed to create agent: {e}. This worker will exit.")
        traceback.print_exc()
        # This worker cannot proceed. It will terminate.
        # Other workers will pick up tasks from the queue.
        return

    while True:
        try:
            task = task_queue.get(timeout=1)
            if task is None:
                # Sentinel value received, so exit. Put it back for other workers.
                task_queue.put(None)
                break
        except queue.Empty:
            # If queue is empty for a bit, just continue waiting for a task or sentinel
            continue

        query, idx = task
        
        try:
            print(f"🚀 [{process_name}] Starting execution for query #{idx+1}: '{query}'")
            start_time = time.time()

            result = agent.execute(goal=query)

            end_time = time.time()
            print(f"✅ [{process_name}] Finished query #{idx+1} in {end_time - start_time:.2f} seconds.")

            final_output = result.get('final_output', 'No output generated.')
            
            result_queue.put({'query': query, 'result': final_output, 'index': idx, 'full_output': result, 'execution_time': end_time - start_time})

        except Exception as e:
            print(f"❌ [{process_name}] An error occurred on query #{idx+1}: {e}")
            traceback.print_exc()
            result_queue.put({'query': query, 'result': f"Error: {e}", 'index': idx})

def main():
    parser = argparse.ArgumentParser(description="Run batch evaluations of the SentientAgent.")
    parser.add_argument("--input-file", type=str, default = "datasets/seal-0.csv", help="Path to the input CSV/parquet file with queries.")
    parser.add_argument("--output-file", default="results.csv", type=str, help="Path to save the results CSV file.")
    parser.add_argument("--query-column", type=str, default="question", help="Name of the column containing queries in the input CSV.")
    parser.add_argument("--num-examples", type=int, default=None, help="Number of examples from dataset to run. If not provided, all examples will be run.")
    # Agent settings
    parser.add_argument("--profile-name", type=str, default="general_agent", help="Agent profile name.")
    parser.add_argument("--enable-hitl-override", action='store_true', help="Enable HITL override.")
    parser.add_argument("--max-concurrent-tasks", type=int, default=10, help="Maximum concurrent tasks for the agent.")
    parser.add_argument("--max-planning-depth", type=int, default=3, help="Maximum planning depth for the agent.")
    
    # Multiprocessing settings
    parser.add_argument("--num-processes", type=int, default=multiprocessing.cpu_count(), help="Number of parallel processes to run.")

    args = parser.parse_args()

    agent_settings = {
        "profile_name": args.profile_name,
        "enable_hitl_override": args.enable_hitl_override,
        "max_concurrent_tasks": args.max_concurrent_tasks,
        "max_planning_depth": args.max_planning_depth,
    }

    try:
        df = pd.read_csv(args.input_file)
        if args.num_examples:
            df = df.iloc[:args.num_examples]
        if args.query_column not in df.columns:
            print(f"Error: Query column '{args.query_column}' not found in {args.input_file}")
            return
        queries = df[args.query_column].tolist()
    except FileNotFoundError:
        print(f"Error: Input file not found at {args.input_file}")
        return
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return

    task_queue = multiprocessing.Queue()
    result_queue = multiprocessing.Queue()

    # Enqueue all tasks with their original index
    for i, query in enumerate(queries):
        task_queue.put((query, i))

    # Add sentinel values to signal workers to stop
    for _ in range(args.num_processes):
        task_queue.put(None)

    processes = []
    print(f"🏁 Starting {args.num_processes} agent worker processes for {len(queries)} queries...")
    for i in range(args.num_processes):
        process = multiprocessing.Process(
            target=agent_worker,
            args=(task_queue, result_queue, agent_settings),
            name=f"AgentWorker-{i+1}"
        )
        processes.append(process)
        process.start()

    # Collect results
    results = []
    num_queries = len(queries)
    while len(results) < num_queries:
        try:
            # Add a timeout to prevent hanging if all workers die
            result = result_queue.get(timeout=300) 
            results.append(result)
            print(f"📊 Progress: {len(results)}/{num_queries} queries completed.")
        except queue.Empty:
            print("Timeout waiting for results. Checking worker status...")
            if not any(p.is_alive() for p in processes):
                print("❌ All worker processes have terminated unexpectedly. Aborting.")
                break
            else:
                print("...Some workers are still alive. Continuing to wait.")


    # Wait for all processes to complete their execution
    for process in processes:
        process.join()

    print("\n✅ All agent executions completed.")

    # Save results
    if results:
        # Sort results by original index to maintain order
        results.sort(key=lambda x: x['index'])
        
        # Create a DataFrame from the results
        results_df = pd.DataFrame(results)
        
        # Prepare the output DataFrame - start with original data
        output_df = df.copy()
        
        # Add all result columns (excluding 'index' since it's just for ordering)
        for col in results_df.columns:
            if col != 'index':  # Skip the index column as it's just for internal ordering
                output_df[col] = results_df[col].values
        
        output_df.to_csv(args.output_file, index=False)
        print(f"💾 Results saved to {args.output_file}")
    else:
        print("No results were generated.")


if __name__ == "__main__":
    # It's good practice to set the start method explicitly for multiprocessing.
    # 'spawn' is safer and more consistent across platforms (required on macOS/Windows).
    try:
        multiprocessing.set_start_method("spawn", force=True)
    except RuntimeError:
        # This will be raised if the context has already been set.
        pass
    main() 