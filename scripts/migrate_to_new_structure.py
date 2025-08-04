#!/usr/bin/env python3
"""
Migrate from legacy directory structure to new organized structure.

This script helps migrate existing data from the old scattered directories
to the new centralized structure.
"""

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from src.sentientresearchagent.config.paths import RuntimePaths


def migrate_directory(source: Path, dest: Path, description: str, dry_run: bool = False):
    """Migrate a directory from source to destination."""
    if not source.exists():
        print(f"  ✓ {description}: Source doesn't exist, skipping")
        return 0
    
    if not source.is_dir():
        print(f"  ✗ {description}: Source is not a directory")
        return 0
    
    items = list(source.iterdir())
    if not items:
        print(f"  ✓ {description}: Source is empty, skipping")
        return 0
    
    if dry_run:
        print(f"  → Would migrate {description}: {len(items)} items from {source} to {dest}")
        return len(items)
    else:
        dest.mkdir(parents=True, exist_ok=True)
        migrated = 0
        
        for item in items:
            dest_item = dest / item.name
            if dest_item.exists():
                print(f"    ⚠ Skipping {item.name} - already exists in destination")
                continue
                
            try:
                if item.is_dir():
                    shutil.copytree(item, dest_item)
                else:
                    shutil.copy2(item, dest_item)
                migrated += 1
                print(f"    ✓ Migrated {item.name}")
            except Exception as e:
                print(f"    ✗ Failed to migrate {item.name}: {e}")
        
        print(f"  ✓ {description}: Migrated {migrated}/{len(items)} items")
        return migrated


def main():
    parser = argparse.ArgumentParser(
        description="Migrate from legacy directory structure to new organized structure"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without actually migrating"
    )
    parser.add_argument(
        "--remove-old",
        action="store_true",
        help="Remove old directories after successful migration"
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create backup of old directories before migration"
    )
    
    args = parser.parse_args()
    
    print("SentientResearchAgent Directory Migration")
    print("=" * 50)
    print()
    
    # Initialize runtime paths
    paths = RuntimePaths.get_default()
    
    # Define migrations
    migrations = [
        # (source, destination, description)
        (Path(".agent_cache"), paths.cache_dir / "agent", "Agent cache"),
        (Path(".agent_projects"), paths.projects_dir, "Agent projects"),
        (Path("project_results"), paths.experiment_results_dir / "legacy", "Project results"),
        (Path("emergency_backups"), paths.experiment_emergency_dir, "Emergency backups"),
    ]
    
    # Create backup if requested
    if args.backup and not args.dry_run:
        backup_dir = Path(f"migration_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        print(f"Creating backup in {backup_dir}...")
        backup_dir.mkdir(exist_ok=True)
        
        for source, _, desc in migrations:
            if source.exists():
                backup_dest = backup_dir / source.name
                try:
                    if source.is_dir():
                        shutil.copytree(source, backup_dest)
                    else:
                        shutil.copy2(source, backup_dest)
                    print(f"  ✓ Backed up {source}")
                except Exception as e:
                    print(f"  ✗ Failed to backup {source}: {e}")
        print()
    
    # Perform migrations
    total_migrated = 0
    print("Migrating directories...")
    
    for source, dest, desc in migrations:
        migrated = migrate_directory(source, dest, desc, args.dry_run)
        total_migrated += migrated
    
    print()
    
    # Migrate log files
    print("Migrating log files...")
    log_files = list(Path(".").glob("*.log"))
    if log_files:
        if args.dry_run:
            print(f"  → Would migrate {len(log_files)} log files to {paths.logs_dir}")
        else:
            paths.logs_dir.mkdir(parents=True, exist_ok=True)
            migrated_logs = 0
            for log_file in log_files:
                dest_log = paths.logs_dir / log_file.name
                if not dest_log.exists():
                    try:
                        shutil.move(str(log_file), str(dest_log))
                        migrated_logs += 1
                        print(f"    ✓ Migrated {log_file.name}")
                    except Exception as e:
                        print(f"    ✗ Failed to migrate {log_file.name}: {e}")
                else:
                    print(f"    ⚠ Skipping {log_file.name} - already exists")
            print(f"  ✓ Log files: Migrated {migrated_logs}/{len(log_files)} files")
    else:
        print("  ✓ No log files to migrate")
    
    print()
    
    # Remove old directories if requested
    if args.remove_old and not args.dry_run and total_migrated > 0:
        print("Removing old directories...")
        for source, _, desc in migrations:
            if source.exists():
                try:
                    shutil.rmtree(source)
                    print(f"  ✓ Removed {source}")
                except Exception as e:
                    print(f"  ✗ Failed to remove {source}: {e}")
        
        # Remove migrated log files
        for log_file in log_files:
            if log_file.exists():
                try:
                    log_file.unlink()
                    print(f"  ✓ Removed {log_file}")
                except Exception as e:
                    print(f"  ✗ Failed to remove {log_file}: {e}")
    
    print()
    print("Migration complete!")
    
    if args.dry_run:
        print("\nThis was a dry run. Run without --dry-run to perform actual migration.")
    elif args.remove_old:
        print("\nOld directories have been removed.")
    else:
        print("\nOld directories have been preserved. Use --remove-old to remove them.")
    
    # Create README files
    if not args.dry_run:
        paths.create_readme()
        print("\nCreated README files in new directories.")


if __name__ == "__main__":
    main()