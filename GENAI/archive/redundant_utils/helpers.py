"""Utility functions."""

import hashlib
from pathlib import Path
from typing import List
import os


def compute_file_hash(filepath: str) -> str:
    """
    Compute MD5 hash of a file.
    
    Args:
        filepath: Path to file
        
    Returns:
        MD5 hash string
    """
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def get_pdf_files(directory: str) -> List[str]:
    """
    Get all PDF files in a directory.
    
    Args:
        directory: Directory path
        
    Returns:
        List of PDF file paths
    """
    pdf_files = []
    for file in Path(directory).glob("*.pdf"):
        pdf_files.append(str(file))
    return sorted(pdf_files)


def ensure_directory(directory: str):
    """
    Ensure directory exists, create if not.
    
    Args:
        directory: Directory path
    """
    Path(directory).mkdir(parents=True, exist_ok=True)


def format_number(value: any) -> str:
    """
    Format number for display.
    
    Args:
        value: Number value
        
    Returns:
        Formatted string
    """
    try:
        num = float(value)
        if num >= 1_000_000_000:
            return f"${num/1_000_000_000:.2f}B"
        elif num >= 1_000_000:
            return f"${num/1_000_000:.2f}M"
        elif num >= 1_000:
            return f"${num/1_000:.2f}K"
        else:
            return f"${num:.2f}"
    except (ValueError, TypeError):
        return str(value)


def truncate_text(text: str, max_length: int = 100) -> str:
    """
    Truncate text to max length.
    
    Args:
        text: Input text
        max_length: Maximum length
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."
