#!/usr/bin/env python3
"""
Archive important experiment results to a permanent location.

Usage:
    python scripts/archive_experiment.py EXPERIMENT_NAME [--archive-dir DIR] [--compress]
"""

import argparse
import json
import shutil
import sys
import tarfile
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from src.sentientresearchagent.config.config import load_config


def create_archive_metadata(exp_dir: Path, archive_reason: str = "") -> Dict[str, Any]:
    """Create metadata for the archived experiment."""
    results_file = exp_dir / "results.json"
    config_file = exp_dir / "config.yaml"
    
    metadata = {
        'original_name': exp_dir.name,
        'archived_at': datetime.now().isoformat(),
        'archive_reason': archive_reason,
        'original_path': str(exp_dir),
        'files': []
    }
    
    # Add file listing
    for file_path in exp_dir.rglob('*'):
        if file_path.is_file():
            metadata['files'].append({
                'path': str(file_path.relative_to(exp_dir)),
                'size': file_path.stat().st_size
            })
    
    # Add summary from results if available
    if results_file.exists():
        with open(results_file, 'r') as f:
            results = json.load(f)
            metadata['summary'] = {
                'timestamp': results.get('timestamp', ''),
                'total_nodes': len(results.get('all_nodes', {})),
                'execution_time': results.get('execution_time', 0),
                'final_answer': results.get('final_answer', '')[:200] + '...' 
                               if len(results.get('final_answer', '')) > 200 
                               else results.get('final_answer', '')
            }
    
    return metadata


def archive_experiment(exp_name: str, base_dir: Path, archive_dir: Path, 
                      compress: bool = False, reason: str = "") -> bool:
    """Archive an experiment to permanent storage."""
    results_dir = base_dir / "results"
    exp_dir = results_dir / exp_name
    
    if not exp_dir.exists():
        print(f"Experiment not found: {exp_name}")
        return False
    
    # Create archive directory if needed
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate archive name with timestamp
    archive_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"{exp_name}_archived_{archive_timestamp}"
    
    if compress:
        # Create compressed archive
        archive_path = archive_dir / f"{archive_name}.tar.gz"
        print(f"Creating compressed archive: {archive_path}")
        
        with tarfile.open(archive_path, "w:gz") as tar:
            # Add experiment directory
            tar.add(exp_dir, arcname=exp_name)
            
            # Add metadata
            metadata = create_archive_metadata(exp_dir, reason)
            metadata_str = json.dumps(metadata, indent=2)
            metadata_info = tarfile.TarInfo(name=f"{exp_name}/ARCHIVE_METADATA.json")
            metadata_info.size = len(metadata_str.encode())
            tar.addfile(metadata_info, fileobj=BytesIO(metadata_str.encode()))
    else:
        # Copy directory
        archive_path = archive_dir / archive_name
        print(f"Copying to archive: {archive_path}")
        
        shutil.copytree(exp_dir, archive_path)
        
        # Add metadata
        metadata = create_archive_metadata(exp_dir, reason)
        with open(archive_path / "ARCHIVE_METADATA.json", 'w') as f:
            json.dump(metadata, f, indent=2)
    
    print(f"Successfully archived: {exp_name}")
    print(f"Archive location: {archive_path}")
    
    # Calculate size
    if archive_path.is_file():
        size = archive_path.stat().st_size / 1024 / 1024
    else:
        size = sum(f.stat().st_size for f in archive_path.rglob('*') if f.is_file()) / 1024 / 1024
    
    print(f"Archive size: {size:.2f} MB")
    
    return True


def main():
    parser = argparse.ArgumentParser(description="Archive experiment results")
    parser.add_argument(
        "experiment_name",
        help="Name of the experiment directory to archive"
    )
    parser.add_argument(
        "--archive-dir",
        type=str,
        default="experiment_archives",
        help="Directory to store archives (default: experiment_archives)"
    )
    parser.add_argument(
        "--compress",
        action="store_true",
        help="Create compressed tar.gz archive"
    )
    parser.add_argument(
        "--reason",
        type=str,
        default="",
        help="Reason for archiving (stored in metadata)"
    )
    parser.add_argument(
        "--base-dir",
        type=str,
        help="Base experiment directory (default: from config)",
        default=None
    )
    parser.add_argument(
        "--remove-original",
        action="store_true",
        help="Remove original experiment after successful archiving"
    )
    
    args = parser.parse_args()
    
    # Need BytesIO for metadata in tar
    if args.compress:
        from io import BytesIO
    
    # Load config
    config = load_config()
    base_dir = Path(args.base_dir) if args.base_dir else Path(config.experiment.base_dir)
    archive_dir = Path(args.archive_dir)
    
    # Archive the experiment
    success = archive_experiment(
        args.experiment_name,
        base_dir,
        archive_dir,
        args.compress,
        args.reason
    )
    
    if success and args.remove_original:
        exp_dir = base_dir / "results" / args.experiment_name
        print(f"\nRemoving original experiment: {exp_dir}")
        shutil.rmtree(exp_dir)
        print("Original experiment removed")


if __name__ == "__main__":
    main()