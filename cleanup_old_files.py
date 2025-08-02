#!/usr/bin/env python
"""
Cleanup script for document retention policy
Keeps only the latest 5 versions of each document per client
Run daily via scheduled task
"""
import os
import re
import sys
import logging
import shutil
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("cleanup_log.txt"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("retention-cleanup")

# Constants
PACKAGES_DIR = Path("packages")
MAX_VERSIONS_TO_KEEP = 5
BACKUP_DIR = Path("packages_backup")

# Document types to manage
DOCUMENT_TYPES = ["161d", "grants_appendix", "commutations_appendix"]


def extract_version(filename):
    """Extract version number from filename, return 1 if no version found"""
    match = re.search(r'_v(\d+)\.(pdf|json)$', filename)
    if match:
        return int(match.group(1))
    return 1  # Default version is 1 (no _v suffix)


def group_files_by_type_and_version(client_dir):
    """
    Group files in client directory by document type and version
    
    Returns:
        dict: {doc_type: {version: path}}
    """
    files_by_type = defaultdict(dict)
    
    if not client_dir.exists() or not client_dir.is_dir():
        return files_by_type
    
    for file_path in client_dir.iterdir():
        if not file_path.is_file():
            continue
            
        filename = file_path.name
        
        # Identify document type
        doc_type = None
        for dt in DOCUMENT_TYPES:
            if dt in filename:
                doc_type = dt
                break
        
        if doc_type:
            version = extract_version(filename)
            files_by_type[doc_type][version] = file_path
    
    return files_by_type


def cleanup_client_directory(client_dir):
    """
    Clean up a client directory, keeping only MAX_VERSIONS_TO_KEEP of each document type
    
    Args:
        client_dir: Path to client directory
    
    Returns:
        int: Number of files deleted
    """
    logger.info(f"Processing client directory: {client_dir}")
    
    # Group files by document type and version
    files_by_type = group_files_by_type_and_version(client_dir)
    
    deleted_count = 0
    
    # Process each document type
    for doc_type, versions in files_by_type.items():
        if len(versions) <= MAX_VERSIONS_TO_KEEP:
            logger.debug(f"Keeping all {len(versions)} versions of {doc_type}")
            continue
            
        # Sort versions from newest to oldest
        sorted_versions = sorted(versions.keys(), reverse=True)
        
        # Keep the newest MAX_VERSIONS_TO_KEEP versions
        versions_to_keep = sorted_versions[:MAX_VERSIONS_TO_KEEP]
        versions_to_delete = sorted_versions[MAX_VERSIONS_TO_KEEP:]
        
        logger.info(f"Document type {doc_type}: keeping versions {versions_to_keep}, deleting {versions_to_delete}")
        
        # Delete old versions
        for version in versions_to_delete:
            file_path = versions[version]
            try:
                file_path.unlink()
                logger.info(f"Deleted: {file_path}")
                deleted_count += 1
            except Exception as e:
                logger.error(f"Failed to delete {file_path}: {e}")
    
    return deleted_count


def backup_packages_dir():
    """Create a backup of the packages directory if needed"""
    if not PACKAGES_DIR.exists():
        logger.warning(f"Packages directory {PACKAGES_DIR} does not exist, skipping backup")
        return False
        
    # Create backup directory if it doesn't exist
    BACKUP_DIR.mkdir(exist_ok=True)
    
    # Create timestamped backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"packages_backup_{timestamp}"
    
    try:
        shutil.copytree(PACKAGES_DIR, backup_path)
        logger.info(f"Created backup at {backup_path}")
        return True
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        return False


def main():
    """Main function to clean up old document versions"""
    logger.info("Starting document retention cleanup")
    
    if not PACKAGES_DIR.exists():
        logger.error(f"Packages directory {PACKAGES_DIR} does not exist")
        return 1
    
    # Optional: Create backup before cleaning
    # backup_packages_dir()
    
    total_deleted = 0
    
    # Process each client directory
    for client_dir in PACKAGES_DIR.iterdir():
        if client_dir.is_dir() and client_dir.name.startswith("client_"):
            deleted = cleanup_client_directory(client_dir)
            total_deleted += deleted
    
    logger.info(f"Cleanup complete. Total files deleted: {total_deleted}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
