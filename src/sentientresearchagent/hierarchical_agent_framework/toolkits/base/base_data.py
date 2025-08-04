from __future__ import annotations

"""Base Data Toolkit Helper Class
=================================

A helper class providing common data management functionality for data-related 
toolkits. This is NOT a toolkit itself, but rather a collection of utilities 
that data toolkits can inherit from or use for common operations.

Key Features:
- Parquet file storage for large datasets
- Configurable data thresholds and storage paths
- Data validation and conversion utilities
- Standardized data directory management
"""

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Union, Optional

import pandas as _pd
from loguru import logger

__all__ = ["BaseDataToolkit"]


class BaseDataToolkit:
    """Helper class for data-intensive toolkit operations.
    
    Provides common functionality for toolkits that handle large datasets and
    need to store data to disk. This class should be inherited by data toolkits
    alongside the main Toolkit class.
    
    Features:
    - Automatic parquet storage for large datasets
    - Configurable data directories and thresholds
    - Data validation and conversion utilities
    - Standardized file naming and organization
    
    Example:
        ```python
        class MyDataToolkit(Toolkit, BaseDataToolkit):
            def __init__(self, data_dir="./data", parquet_threshold=1000, **kwargs):
                # Initialize Toolkit
                super().__init__(**toolkit_kwargs)
                
                # Initialize BaseDataToolkit helpers
                self._init_data_helpers(data_dir, parquet_threshold)
                
            async def get_large_dataset(self, symbol: str):
                data = await self._fetch_large_data(symbol)
                
                if self._should_store_as_parquet(data):
                    file_path = self._store_parquet(data, f"dataset_{symbol}")
                    return {"success": True, "file_path": file_path}
                else:
                    return {"success": True, "data": data}
        ```
    """

    def _init_data_helpers(
        self,
        data_dir: str | Path,
        parquet_threshold: int = 1000,
        file_prefix: str = "",
    ) -> None:
        """Initialize data management helpers.
        
        Args:
            data_dir: Directory path for storing parquet files
            parquet_threshold: Minimum size to trigger parquet storage
            file_prefix: Optional prefix for all generated files
        """
        # Ensure data_dir is a Path object
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self._parquet_threshold = parquet_threshold
        self._file_prefix = file_prefix
        
        logger.debug(f"Initialized data helpers: dir={self.data_dir}, threshold={parquet_threshold}")

    def _store_parquet(
        self, 
        data: Union[List[Dict[str, Any]], _pd.DataFrame], 
        prefix: str,
        subdirectory: Optional[str] = None,
    ) -> str:
        """Store data as a parquet file and return the path.
        
        Args:
            data: Data to store (list of dicts or DataFrame)
            prefix: Filename prefix for the parquet file
            subdirectory: Optional subdirectory within data_dir
            
        Returns:
            str: Full path to the created parquet file
            
        Raises:
            ValueError: If data is empty or invalid
            IOError: If file cannot be written
            
        Example:
            ```python
            # Store list of dicts
            data = [{"symbol": "BTCUSDT", "price": 50000}, ...]
            path = self._store_parquet(data, "prices_btc")
            
            # Store DataFrame with subdirectory
            df = pd.DataFrame(data)
            path = self._store_parquet(df, "order_book", subdirectory="binance")
            ```
        """
        if isinstance(data, list):
            if not data:
                raise ValueError("Cannot store empty list as parquet")
            df = _pd.DataFrame(data)
        else:
            df = data
        
        if df.empty:
            raise ValueError("Cannot store empty DataFrame as parquet")
        
        # Prepare file path
        ts = int(time.time())
        filename = f"{self._file_prefix}{prefix}_{ts}.parquet"
        
        if subdirectory:
            file_dir = self.data_dir / subdirectory
            file_dir.mkdir(parents=True, exist_ok=True)
            file_path = file_dir / filename
        else:
            file_path = self.data_dir / filename
        
        try:
            df.to_parquet(file_path, compression='snappy', index=False)
            logger.info(f"Stored {len(df)} records to: {file_path}")
            return str(file_path)
        except Exception as e:
            logger.error(f"Failed to write parquet file {file_path}: {e}")
            raise IOError(f"Cannot write parquet file: {e}")

    def _should_store_as_parquet(
        self, 
        data: Union[List, _pd.DataFrame, Dict[str, Any]]
    ) -> bool:
        """Check if data should be stored as parquet based on size threshold.
        
        Args:
            data: Data to check (list, DataFrame, or dict with length info)
            
        Returns:
            bool: True if data should be stored as parquet, False otherwise
            
        Example:
            ```python
            large_data = [{"id": i} for i in range(5000)]
            should_store = self._should_store_as_parquet(large_data)  # True
            
            small_data = [{"id": 1}, {"id": 2}]
            should_store = self._should_store_as_parquet(small_data)  # False
            ```
        """
        if isinstance(data, list):
            return len(data) > self._parquet_threshold
        elif isinstance(data, _pd.DataFrame):
            return len(data) > self._parquet_threshold
        elif isinstance(data, dict):
            # For response dicts that might contain data arrays
            if 'data' in data and isinstance(data['data'], (list, _pd.DataFrame)):
                return self._should_store_as_parquet(data['data'])
            # Check if dict has length-like fields
            for key in ['count', 'size', 'length', 'total']:
                if key in data and isinstance(data[key], int):
                    return data[key] > self._parquet_threshold
        
        return False

    def _convert_to_dataframe(
        self, 
        data: Union[List[Dict[str, Any]], Dict[str, Any], _pd.DataFrame],
        index_column: Optional[str] = None,
    ) -> _pd.DataFrame:
        """Convert various data formats to a pandas DataFrame.
        
        Args:
            data: Data to convert
            index_column: Optional column to use as DataFrame index
            
        Returns:
            pd.DataFrame: Converted DataFrame
            
        Raises:
            ValueError: If data format is not supported
            
        Example:
            ```python
            # Convert list of dicts
            data = [{"symbol": "BTC", "price": 50000}, {"symbol": "ETH", "price": 3000}]
            df = self._convert_to_dataframe(data, index_column="symbol")
            
            # Convert nested dict
            data = {"symbols": ["BTC", "ETH"], "prices": [50000, 3000]}
            df = self._convert_to_dataframe(data)
            ```
        """
        if isinstance(data, _pd.DataFrame):
            df = data.copy()
        elif isinstance(data, list):
            if not data:
                raise ValueError("Cannot convert empty list to DataFrame")
            df = _pd.DataFrame(data)
        elif isinstance(data, dict):
            # Try to convert dict to DataFrame
            try:
                df = _pd.DataFrame(data)
            except Exception as e:
                raise ValueError(f"Cannot convert dict to DataFrame: {e}")
        else:
            raise ValueError(f"Unsupported data type for DataFrame conversion: {type(data)}")
        
        if index_column and index_column in df.columns:
            df = df.set_index(index_column)
        
        return df

    # REMOVED: _validate_data_structure - Use DataValidator.validate_structure() from utils instead

    def _get_data_summary(
        self, 
        data: Union[List, _pd.DataFrame, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate a summary of data for logging and responses.
        
        Args:
            data: Data to summarize
            
        Returns:
            dict: Data summary with size, type, and other metadata
            
        Example:
            ```python
            summary = self._get_data_summary(large_dataset)
            logger.info(f"Processed data: {summary}")
            # Output: {"type": "list", "size": 5000, "memory_mb": 12.5, ...}
            ```
        """
        summary = {
            "type": type(data).__name__,
            "timestamp": int(time.time()),
        }
        
        if isinstance(data, (list, _pd.DataFrame)):
            summary["size"] = len(data)
            summary["empty"] = len(data) == 0
            
            if isinstance(data, _pd.DataFrame):
                summary["columns"] = list(data.columns)
                summary["memory_mb"] = round(data.memory_usage(deep=True).sum() / (1024 * 1024), 2)
            elif isinstance(data, list) and data:
                # Estimate memory for list
                import sys
                summary["memory_mb"] = round(sys.getsizeof(data) / (1024 * 1024), 2)
                
                # Analyze structure of first item
                if isinstance(data[0], dict):
                    summary["fields"] = list(data[0].keys())
                    
        elif isinstance(data, dict):
            summary["keys"] = list(data.keys())
            
            # Check for nested data
            for key, value in data.items():
                if isinstance(value, (list, _pd.DataFrame)) and hasattr(value, '__len__'):
                    summary[f"{key}_size"] = len(value)
        
        summary["should_store_parquet"] = self._should_store_as_parquet(data)
        
        return summary

    # =========================================================================
    # Standardized Data Response Methods  
    # =========================================================================
    
    # REMOVED: _build_data_response - Use ResponseBuilder.build_data_response_with_storage() from utils instead

    # REMOVED: _generate_data_filename - Use FileNameGenerator.generate_data_filename() from utils instead

    # REMOVED: _build_data_response_with_analysis - Use ResponseBuilder.build_data_response_with_storage() from utils instead

    # REMOVED: _extract_ohlcv_data - Not used, OHLCV extraction handled directly in individual toolkit implementations

    def _clean_data_directory(
        self, 
        max_age_hours: int = 24,
        pattern: str = "*.parquet",
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Clean old files from the data directory.
        
        Args:
            max_age_hours: Maximum age of files to keep (in hours)
            pattern: File pattern to match for cleanup
            dry_run: If True, only report what would be deleted
            
        Returns:
            dict: Cleanup results with counts and file lists
            
        Example:
            ```python
            # Clean files older than 48 hours
            result = self._clean_data_directory(max_age_hours=48)
            logger.info(f"Cleaned {result['deleted_count']} old files")
            
            # Dry run to see what would be deleted
            result = self._clean_data_directory(dry_run=True)
            ```
        """
        import glob
        import time
        
        if not hasattr(self, 'data_dir'):
            raise ValueError("Data directory not initialized. Call _init_data_helpers first.")
        
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        # Find matching files
        pattern_path = self.data_dir / pattern
        matching_files = glob.glob(str(pattern_path), recursive=True)
        
        old_files = []
        total_size = 0
        
        for file_path in matching_files:
            file_stat = os.stat(file_path)
            file_age = current_time - file_stat.st_mtime
            
            if file_age > max_age_seconds:
                old_files.append({
                    "path": file_path,
                    "age_hours": round(file_age / 3600, 1),
                    "size_mb": round(file_stat.st_size / (1024 * 1024), 2),
                })
                total_size += file_stat.st_size
        
        deleted_count = 0
        if not dry_run:
            for file_info in old_files:
                try:
                    os.remove(file_info["path"])
                    deleted_count += 1
                    logger.debug(f"Deleted old file: {file_info['path']}")
                except Exception as e:
                    logger.error(f"Failed to delete {file_info['path']}: {e}")
        
        return {
            "total_files_checked": len(matching_files),
            "old_files_found": len(old_files),
            "deleted_count": deleted_count,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "dry_run": dry_run,
            "max_age_hours": max_age_hours,
            "old_files": old_files if dry_run else [],
        }