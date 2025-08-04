#!/usr/bin/env python3
"""
Clean old experiment results based on retention policy.

Usage:
    python scripts/clean_old_experiments.py [--days DAYS] [--dry-run]
"""

import argparse
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from src.sentientresearchagent.config.config import load_config


def parse_timestamp(dirname: str, format_str: str) -> datetime:
    """Parse timestamp from directory name."""
    try:
        # Extract timestamp part (assumes format: {timestamp}_{name})
        timestamp_part = dirname.split('_')[0] + '_' + dirname.split('_')[1]
        return datetime.strptime(timestamp_part, format_str)
    except:
        return None


def clean_old_experiments(base_dir: Path, retention_days: int, dry_run: bool = False):
    """Clean experiment directories older than retention_days."""
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    
    results_dir = base_dir / "results"
    if not results_dir.exists():
        print(f"Results directory not found: {results_dir}")
        return
    
    removed_count = 0
    total_size = 0
    
    # Get config to know timestamp format
    config = load_config()
    timestamp_format = config.experiment.timestamp_format
    
    for item in results_dir.iterdir():
        if not item.is_dir():
            continue
            
        # Try to parse timestamp from directory name
        timestamp = parse_timestamp(item.name, timestamp_format)
        if not timestamp:
            print(f"Skipping {item.name} - couldn't parse timestamp")
            continue
            
        if timestamp < cutoff_date:
            # Calculate size
            size = sum(f.stat().st_size for f in item.rglob('*') if f.is_file())
            total_size += size
            
            if dry_run:
                print(f"Would remove: {item.name} (created: {timestamp.date()}, size: {size/1024/1024:.2f} MB)")
            else:
                print(f"Removing: {item.name} (created: {timestamp.date()}, size: {size/1024/1024:.2f} MB)")
                shutil.rmtree(item)
            
            removed_count += 1
    
    print(f"\nSummary:")
    print(f"- {'Would remove' if dry_run else 'Removed'}: {removed_count} experiments")
    print(f"- Total space {'to be freed' if dry_run else 'freed'}: {total_size/1024/1024:.2f} MB")
    print(f"- Retention period: {retention_days} days")


def main():
    parser = argparse.ArgumentParser(description="Clean old experiment results")
    parser.add_argument(
        "--days", 
        type=int, 
        help="Number of days to retain (overrides config)",
        default=None
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true",
        help="Show what would be deleted without actually deleting"
    )
    parser.add_argument(
        "--base-dir",
        type=str,
        help="Base experiment directory (default: from config)",
        default=None
    )
    
    args = parser.parse_args()
    
    # Load config
    config = load_config()
    
    # Determine parameters
    base_dir = Path(args.base_dir) if args.base_dir else Path(config.experiment.base_dir)
    retention_days = args.days if args.days is not None else config.experiment.retention_days
    
    print(f"Cleaning experiments in: {base_dir}")
    print(f"Retention period: {retention_days} days")
    print(f"Dry run: {args.dry_run}\n")
    
    clean_old_experiments(base_dir, retention_days, args.dry_run)


if __name__ == "__main__":
    main()