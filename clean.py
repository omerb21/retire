#!/usr/bin/env python
"""
Repository cleanup script to remove unnecessary artifacts.
Run this script to clean up build artifacts, caches, and other temporary files.
"""

import os
import shutil
import glob
from pathlib import Path


def get_size_format(bytes, suffix="B"):
    """Convert bytes to a human-readable format"""
    factor = 1024
    for unit in ["", "K", "M", "G", "T", "P"]:
        if bytes < factor:
            return f"{bytes:.2f} {unit}{suffix}"
        bytes /= factor
    return f"{bytes:.2f} Y{suffix}"


def remove_directory(path):
    """Remove a directory and all its contents"""
    try:
        if os.path.exists(path):
            print(f"Removing {path}...")
            shutil.rmtree(path)
            return True
        return False
    except Exception as e:
        print(f"Error removing {path}: {e}")
        return False


def remove_file(path):
    """Remove a file"""
    try:
        if os.path.exists(path):
            print(f"Removing {path}...")
            os.remove(path)
            return True
        return False
    except Exception as e:
        print(f"Error removing {path}: {e}")
        return False


def clean_artifacts(root_dir):
    """Clean up build artifacts, caches, and temporary files"""
    total_size_saved = 0
    total_files_removed = 0
    total_dirs_removed = 0

    # Directories to clean
    dirs_to_clean = [
        "**/__pycache__",
        "**/.pytest_cache",
        "**/node_modules",
        "**/build",
        "**/dist",
        "**/.coverage",
        "**/htmlcov",
        "**/.eggs",
        "**/*.egg-info",
    ]

    # Files to clean
    files_to_clean = [
        "**/*.pyc",
        "**/*.pyo",
        "**/*.pyd",
        "**/*.so",
        "**/*.coverage",
        "**/*.log",
        "**/*.db",
        "**/*.sqlite3",
    ]

    # Process directories
    for pattern in dirs_to_clean:
        for path in glob.glob(os.path.join(root_dir, pattern), recursive=True):
            if os.path.isdir(path):
                size = sum(
                    os.path.getsize(os.path.join(dirpath, filename))
                    for dirpath, _, filenames in os.walk(path)
                    for filename in filenames
                    if os.path.exists(os.path.join(dirpath, filename))
                )
                if remove_directory(path):
                    total_size_saved += size
                    total_dirs_removed += 1

    # Process files
    for pattern in files_to_clean:
        for path in glob.glob(os.path.join(root_dir, pattern), recursive=True):
            if os.path.isfile(path):
                size = os.path.getsize(path)
                if remove_file(path):
                    total_size_saved += size
                    total_files_removed += 1

    return total_size_saved, total_files_removed, total_dirs_removed


if __name__ == "__main__":
    root_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"Cleaning up repository at {root_dir}...")
    
    size_saved, files_removed, dirs_removed = clean_artifacts(root_dir)
    
    print("\nCleanup Summary:")
    print(f"Directories removed: {dirs_removed}")
    print(f"Files removed: {files_removed}")
    print(f"Total space saved: {get_size_format(size_saved)}")
    print("\nCleanup completed successfully!")
