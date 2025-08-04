#!/usr/bin/env python3
"""
Interactive log viewer for SentientResearchAgent logs.

Features:
- Tail logs in real-time
- Filter by log level
- Search for specific patterns
- Colorized output
"""

import argparse
import re
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add color support
try:
    from colorama import init, Fore, Style
    init()
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False


# Log level colors
LEVEL_COLORS = {
    "TRACE": "CYAN",
    "DEBUG": "BLUE",
    "INFO": "GREEN",
    "SUCCESS": "GREEN",
    "WARNING": "YELLOW",
    "ERROR": "RED",
    "CRITICAL": "MAGENTA",
}


def colorize(text: str, color: str) -> str:
    """Add color to text if colorama is available."""
    if not HAS_COLOR:
        return text
    
    color_map = {
        "CYAN": Fore.CYAN,
        "BLUE": Fore.BLUE,
        "GREEN": Fore.GREEN,
        "YELLOW": Fore.YELLOW,
        "RED": Fore.RED,
        "MAGENTA": Fore.MAGENTA,
        "DIM": Style.DIM,
    }
    
    return f"{color_map.get(color, '')}{text}{Style.RESET_ALL}"


def parse_log_line(line: str) -> dict:
    """Parse a log line into components."""
    # Pattern for file logs: YYYY-MM-DD HH:MM:SS.SSS | LEVEL | module | function | message
    pattern = r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\s*\|\s*(\w+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*(.*)$'
    match = re.match(pattern, line)
    
    if match:
        return {
            'timestamp': match.group(1),
            'level': match.group(2).strip(),
            'module': match.group(3).strip(),
            'function': match.group(4).strip(),
            'message': match.group(5).strip()
        }
    return None


def format_log_line(parsed: dict, show_module: bool = True) -> str:
    """Format a parsed log line with colors."""
    level = parsed['level']
    color = LEVEL_COLORS.get(level, "GREEN")
    
    # Format timestamp
    timestamp = colorize(parsed['timestamp'][11:19], "DIM")  # Just HH:MM:SS
    
    # Format level with color
    level_str = colorize(f"{level:<8}", color)
    
    # Format module (optional)
    module_str = ""
    if show_module:
        module = parsed['module']
        if len(module) > 30:
            module = "..." + module[-27:]
        module_str = colorize(f"{module:<30}", "CYAN") + " | "
    
    # Format message
    message = parsed['message']
    
    # Add emojis for certain keywords
    emoji_map = {
        "start": "🚀",
        "success": "✅",
        "error": "❌",
        "warning": "⚠️",
        "complete": "✔️",
        "failed": "❌",
    }
    
    for keyword, emoji in emoji_map.items():
        if keyword in message.lower():
            message = f"{emoji} {message}"
            break
    
    return f"{timestamp} | {level_str} | {module_str}{message}"


def tail_file(file_path: Path, level_filter: Optional[str] = None, 
              search_pattern: Optional[str] = None, show_module: bool = True):
    """Tail a log file with filtering."""
    if not file_path.exists():
        print(f"Log file not found: {file_path}")
        return
    
    # Compile search pattern if provided
    search_regex = None
    if search_pattern:
        try:
            search_regex = re.compile(search_pattern, re.IGNORECASE)
        except re.error:
            print(f"Invalid search pattern: {search_pattern}")
            return
    
    # Get log levels to show
    level_order = ["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]
    if level_filter:
        try:
            min_level_idx = level_order.index(level_filter.upper())
            allowed_levels = level_order[min_level_idx:]
        except ValueError:
            print(f"Invalid log level: {level_filter}")
            return
    else:
        allowed_levels = level_order
    
    print(f"📋 Viewing logs from: {file_path}")
    print(f"🔍 Filter: level >= {level_filter or 'ALL'}")
    if search_pattern:
        print(f"🔎 Search: {search_pattern}")
    print("-" * 80)
    
    # Open file and seek to end
    with open(file_path, 'r') as f:
        # Show last 20 lines initially
        lines = f.readlines()
        start_idx = max(0, len(lines) - 20)
        
        for line in lines[start_idx:]:
            process_line(line, allowed_levels, search_regex, show_module)
        
        # Continue tailing
        try:
            while True:
                line = f.readline()
                if line:
                    process_line(line, allowed_levels, search_regex, show_module)
                else:
                    time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n\n✋ Log viewer stopped")


def process_line(line: str, allowed_levels: list, search_regex: Optional[re.Pattern], 
                 show_module: bool):
    """Process and display a single log line."""
    line = line.strip()
    if not line:
        return
    
    parsed = parse_log_line(line)
    if not parsed:
        # Unparsed line - might be continuation of previous message
        print(colorize(f"    {line}", "DIM"))
        return
    
    # Check level filter
    if parsed['level'] not in allowed_levels:
        return
    
    # Check search filter
    if search_regex and not search_regex.search(line):
        return
    
    # Format and print
    formatted = format_log_line(parsed, show_module)
    print(formatted)


def main():
    parser = argparse.ArgumentParser(description="View SentientResearchAgent logs")
    parser.add_argument(
        "log_file",
        nargs="?",
        help="Log file to view (default: runtime/logs/sentient.log)"
    )
    parser.add_argument(
        "-l", "--level",
        choices=["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Minimum log level to show"
    )
    parser.add_argument(
        "-s", "--search",
        help="Search pattern (regex)"
    )
    parser.add_argument(
        "-m", "--no-module",
        action="store_true",
        help="Hide module names"
    )
    parser.add_argument(
        "-f", "--follow",
        action="store_true",
        help="Follow log file (tail -f)"
    )
    
    args = parser.parse_args()
    
    # Determine log file
    if args.log_file:
        log_path = Path(args.log_file)
    else:
        log_path = Path("runtime/logs/sentient.log")
    
    if args.follow:
        tail_file(log_path, args.level, args.search, not args.no_module)
    else:
        # Just show existing content
        if not log_path.exists():
            print(f"Log file not found: {log_path}")
            return
        
        with open(log_path, 'r') as f:
            for line in f:
                process_line(
                    line,
                    ["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"],
                    re.compile(args.search, re.IGNORECASE) if args.search else None,
                    not args.no_module
                )


if __name__ == "__main__":
    main()