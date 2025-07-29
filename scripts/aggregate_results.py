#!/usr/bin/env python3
"""
Aggregate results from multiple experiment runs.

Usage:
    python scripts/aggregate_results.py [--pattern PATTERN] [--output OUTPUT]
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Any

import pandas as pd

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from src.sentientresearchagent.config.config import load_config


def load_experiment_results(results_path: Path) -> Dict[str, Any]:
    """Load results from a single experiment."""
    results_file = results_path / "results.json"
    if not results_file.exists():
        return None
    
    with open(results_file, 'r') as f:
        return json.load(f)


def aggregate_results(base_dir: Path, pattern: str = "*") -> pd.DataFrame:
    """Aggregate results from multiple experiments matching pattern."""
    results_dir = base_dir / "results"
    if not results_dir.exists():
        print(f"Results directory not found: {results_dir}")
        return pd.DataFrame()
    
    all_results = []
    
    for exp_dir in results_dir.glob(pattern):
        if not exp_dir.is_dir():
            continue
            
        results = load_experiment_results(exp_dir)
        if not results:
            print(f"No results.json found in {exp_dir.name}")
            continue
            
        # Extract key metrics
        experiment_data = {
            'experiment_name': exp_dir.name,
            'timestamp': results.get('timestamp', ''),
            'config_name': results.get('config', {}).get('experiment', {}).get('name', ''),
            'profile': results.get('config', {}).get('active_profile_name', ''),
            'total_time': results.get('execution_time', 0),
            'total_nodes': len(results.get('all_nodes', {})),
            'completed_nodes': sum(1 for n in results.get('all_nodes', {}).values() 
                                 if n.get('status') == 'completed'),
            'failed_nodes': sum(1 for n in results.get('all_nodes', {}).values() 
                              if n.get('status') == 'failed'),
        }
        
        # Add custom metrics if present
        if 'metrics' in results:
            experiment_data.update(results['metrics'])
        
        # Add final answer if present
        if 'final_answer' in results:
            experiment_data['final_answer'] = results['final_answer']
            
        all_results.append(experiment_data)
    
    return pd.DataFrame(all_results)


def generate_summary_stats(df: pd.DataFrame) -> Dict[str, Any]:
    """Generate summary statistics from aggregated results."""
    if df.empty:
        return {}
        
    summary = {
        'total_experiments': len(df),
        'unique_configs': df['config_name'].nunique(),
        'unique_profiles': df['profile'].nunique(),
        'avg_execution_time': df['total_time'].mean(),
        'avg_nodes_per_experiment': df['total_nodes'].mean(),
        'success_rate': (df['failed_nodes'] == 0).mean() * 100,
        'avg_completion_rate': (df['completed_nodes'] / df['total_nodes']).mean() * 100,
    }
    
    # Group by profile
    profile_stats = []
    for profile in df['profile'].unique():
        profile_df = df[df['profile'] == profile]
        profile_stats.append({
            'profile': profile,
            'count': len(profile_df),
            'avg_time': profile_df['total_time'].mean(),
            'avg_nodes': profile_df['total_nodes'].mean(),
            'success_rate': (profile_df['failed_nodes'] == 0).mean() * 100,
        })
    
    summary['profile_stats'] = profile_stats
    
    return summary


def main():
    parser = argparse.ArgumentParser(description="Aggregate experiment results")
    parser.add_argument(
        "--pattern", 
        type=str,
        default="*",
        help="Pattern to match experiment directories (e.g., '*research*')"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file for aggregated results (CSV or JSON)",
        default="aggregated_results.csv"
    )
    parser.add_argument(
        "--base-dir",
        type=str,
        help="Base experiment directory (default: from config)",
        default=None
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print summary statistics"
    )
    
    args = parser.parse_args()
    
    # Load config
    config = load_config()
    base_dir = Path(args.base_dir) if args.base_dir else Path(config.experiment.base_dir)
    
    print(f"Aggregating results from: {base_dir}")
    print(f"Pattern: {args.pattern}\n")
    
    # Aggregate results
    df = aggregate_results(base_dir, args.pattern)
    
    if df.empty:
        print("No results found matching the pattern.")
        return
    
    print(f"Found {len(df)} experiments")
    
    # Save results
    output_path = Path(args.output)
    if output_path.suffix == '.json':
        df.to_json(output_path, orient='records', indent=2)
    else:
        df.to_csv(output_path, index=False)
    
    print(f"Results saved to: {output_path}")
    
    # Print summary if requested
    if args.summary:
        print("\n=== Summary Statistics ===")
        summary = generate_summary_stats(df)
        
        print(f"Total experiments: {summary['total_experiments']}")
        print(f"Unique configurations: {summary['unique_configs']}")
        print(f"Average execution time: {summary['avg_execution_time']:.2f}s")
        print(f"Average nodes per experiment: {summary['avg_nodes_per_experiment']:.1f}")
        print(f"Overall success rate: {summary['success_rate']:.1f}%")
        print(f"Average completion rate: {summary['avg_completion_rate']:.1f}%")
        
        print("\n=== Profile Statistics ===")
        for profile_stat in summary['profile_stats']:
            print(f"\nProfile: {profile_stat['profile']}")
            print(f"  Experiments: {profile_stat['count']}")
            print(f"  Avg time: {profile_stat['avg_time']:.2f}s")
            print(f"  Avg nodes: {profile_stat['avg_nodes']:.1f}")
            print(f"  Success rate: {profile_stat['success_rate']:.1f}%")


if __name__ == "__main__":
    main()