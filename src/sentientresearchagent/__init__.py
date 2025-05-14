from loguru import logger
import sys
import os # For creating directories

log_file_name = "current_run.log" # Name of the log file

# 1. Remove any existing handlers (important if you re-run this cell)
try:
    logger.remove()
except ValueError:
    pass

# 2. Add a handler for Jupyter Notebook cell output (colored)
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss.SSS}</green> | "
           "<level>{level: <8}</level> | "
           "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
           "<level>{message}</level>",
    level="DEBUG",    # Or "INFO" if you prefer less verbose console output
    colorize=True,
    enqueue=False
)

# 3. Add a file handler that overwrites and logs neatly to the specified folder
logger.add(
    log_file_name,
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}", # Clean format for file
    level="DEBUG",          # Typically, you want all details in the file log
    colorize=False,         # No color codes in the log file
    mode="w",               # KEY: "w" for overwrite mode
    enqueue=True,           # Good for performance with file I/O
    encoding="utf-8"        # Explicitly set encoding, good practice
)