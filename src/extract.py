# CSV extraction and file hashing module
import os
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Union
import pandas as pd

logger = logging.getLogger("DataExtractor")


# Calculate SHA256 file hash
def compute_sha256(file_path: Union[str, Path]) -> str:
    path = Path(file_path)
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


# Extract file size, hash, and timestamp
def get_file_metadata(file_path: Union[str, Path]) -> Dict[str, Union[str, int]]:
    path = Path(file_path)
    file_stat = path.stat()
    file_hash = compute_sha256(path)
            
    return {
        "file_name": path.name,
        "file_path": str(path.resolve()),
        "file_size_bytes": file_stat.st_size,
        "file_hash_sha256": file_hash,
        "extracted_at": datetime.now().isoformat(),
    }


# Read CSV file with encoding fallback
def read_csv_file(file_path: Union[str, Path]) -> Tuple[pd.DataFrame, Dict[str, Union[str, int]]]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    metadata = get_file_metadata(path)
    logger.info("Extracting data from: %s", path.name)

    # Try common encodings
    encodings = ["utf-8", "utf-8-sig", "latin1", "cp1252"]
    df = None
    for enc in encodings:
        try:
            df = pd.read_csv(path, encoding=enc, dtype=str)
            logger.info("Successfully read %s with %s encoding (%d rows, %d cols)", path.name, enc, len(df), len(df.columns))
            break
        except (UnicodeDecodeError, Exception) as err:
            logger.debug("Failed reading with %s: %s", enc, err)

    if df is None:
        raise ValueError(f"Could not parse CSV file {path.name} with standard encodings.")

    metadata["row_count"] = len(df)
    metadata["column_count"] = len(df.columns)
    metadata["columns"] = list(df.columns)
    df["_source_file"] = path.name

    return df, metadata


# Read all CSV files in data folder
def read_all_raw_files(data_dir: Union[str, Path] = "data/raw") -> Tuple[pd.DataFrame, List[Dict[str, Union[str, int]]]]:
    raw_path = Path(data_dir)
    if not raw_path.exists():
        raw_path.mkdir(parents=True, exist_ok=True)
        return pd.DataFrame(), []

    csv_files = sorted(list(raw_path.glob("*.csv")))
    if not csv_files:
        return pd.DataFrame(), []

    all_dfs = []
    all_metadata = []

    for file_path in csv_files:
        try:
            df, meta = read_csv_file(file_path)
            all_dfs.append(df)
            all_metadata.append(meta)
        except Exception as exc:
            logger.error("Failed to extract %s: %s", file_path.name, exc)

    if not all_dfs:
        return pd.DataFrame(), all_metadata

    combined_df = pd.concat(all_dfs, ignore_index=True)
    logger.info("Extracted %d total raw records from %d files.", len(combined_df), len(all_dfs))
    return combined_df, all_metadata
