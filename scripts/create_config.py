#!/usr/bin/env python3
"""
Utility script to create and manage Sentient Research Agent configurations.
"""

import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sentientresearchagent.config import create_sample_config
from sentientresearchagent.config_utils import auto_load_config, validate_config, get_config_info

def main():
    """Main CLI function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Sentient Research Agent Configuration Utility")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Create command
    create_parser = subparsers.add_parser('create', help='Create a sample configuration file')
    create_parser.add_argument('path', help='Path where to create the configuration file')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate current configuration')
    validate_parser.add_argument('--config', help='Path to configuration file (optional)')
    
    # Info command
    info_parser = subparsers.add_parser('info', help='Show current configuration info')
    info_parser.add_argument('--config', help='Path to configuration file (optional)')
    
    args = parser.parse_args()
    
    if args.command == 'create':
        create_sample_config(args.path)
        print(f"✅ Sample configuration created at {args.path}")
        print("Edit the file to customize your settings!")
        
    elif args.command == 'validate':
        try:
            if args.config:
                from sentientresearchagent.config import SentientConfig
                config = SentientConfig.from_yaml(args.config)
            else:
                config = auto_load_config()
            
            validation = validate_config(config)
            
            if validation['valid']:
                print("✅ Configuration is valid!")
            else:
                print("❌ Configuration has issues:")
                for issue in validation['issues']:
                    print(f"  - {issue}")
            
            if validation['warnings']:
                print("⚠️  Warnings:")
                for warning in validation['warnings']:
                    print(f"  - {warning}")
                    
        except Exception as e:
            print(f"❌ Error validating configuration: {e}")
            
    elif args.command == 'info':
        try:
            if args.config:
                from sentientresearchagent.config import SentientConfig
                config = SentientConfig.from_yaml(args.config)
            else:
                config = auto_load_config()
            
            info = get_config_info(config)
            print("📋 Configuration Info:")
            for key, value in info.items():
                print(f"  {key}: {value}")
                
        except Exception as e:
            print(f"❌ Error getting configuration info: {e}")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 