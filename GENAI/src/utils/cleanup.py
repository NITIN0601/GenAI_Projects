"""
Cleanup utilities for clearing caches and temporary files.

Usage:
    # From Python
    from src.utils.cleanup import clear_all_cache
    clear_all_cache()
    
    # From command line
    python -m src.utils.cleanup
    
    # Or via main.py
    python main.py cleanup
"""

import os
import shutil
from pathlib import Path
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


def clear_pycache(root_dir: str = None, dry_run: bool = False) -> int:
    """
    Remove all __pycache__ directories.
    
    Args:
        root_dir: Root directory to search (default: project root)
        dry_run: If True, only print what would be deleted
        
    Returns:
        Number of directories removed
    """
    if root_dir is None:
        from config.settings import settings
        root_dir = settings.PROJECT_ROOT
    
    root = Path(root_dir)
    count = 0
    
    for pycache in root.rglob("__pycache__"):
        if pycache.is_dir():
            if dry_run:
                print(f"  Would delete: {pycache}")
            else:
                shutil.rmtree(pycache)
                logger.debug(f"Removed: {pycache}")
            count += 1
    
    return count


def clear_pyc_files(root_dir: str = None, dry_run: bool = False) -> int:
    """
    Remove all .pyc and .pyo files.
    
    Args:
        root_dir: Root directory to search
        dry_run: If True, only print what would be deleted
        
    Returns:
        Number of files removed
    """
    if root_dir is None:
        from config.settings import settings
        root_dir = settings.PROJECT_ROOT
    
    root = Path(root_dir)
    count = 0
    
    for pattern in ["*.pyc", "*.pyo"]:
        for pyc_file in root.rglob(pattern):
            if pyc_file.is_file():
                if dry_run:
                    print(f"  Would delete: {pyc_file}")
                else:
                    pyc_file.unlink()
                    logger.debug(f"Removed: {pyc_file}")
                count += 1
    
    return count


def clear_application_cache(dry_run: bool = False) -> Dict[str, int]:
    """
    Clear all application caches (extraction, embedding, query).
    
    Args:
        dry_run: If True, only print what would be deleted
        
    Returns:
        Dictionary with counts per cache type
    """
    from src.core.paths import get_paths
    
    paths = get_paths()
    cache_dirs = {
        'extraction': paths.extraction_cache_dir,
        'embeddings': paths.embedding_cache_dir,
        'queries': paths.query_cache_dir,
    }
    
    results = {}
    
    for cache_name, cache_dir in cache_dirs.items():
        count = 0
        if cache_dir.exists():
            for item in cache_dir.iterdir():
                if item.is_file():
                    if dry_run:
                        print(f"  Would delete: {item}")
                    else:
                        item.unlink()
                        logger.debug(f"Removed: {item}")
                    count += 1
        results[cache_name] = count
    
    return results


def clear_faiss_index(dry_run: bool = False) -> bool:
    """
    Clear FAISS vector index.
    
    Args:
        dry_run: If True, only print what would be deleted
        
    Returns:
        True if index was cleared
    """
    from config.settings import settings
    
    faiss_dir = Path(settings.PROJECT_ROOT) / 'faiss_index'
    
    if faiss_dir.exists():
        if dry_run:
            print(f"  Would delete: {faiss_dir}")
            return True
        else:
            shutil.rmtree(faiss_dir)
            logger.info(f"Cleared FAISS index: {faiss_dir}")
            return True
    
    return False


def clear_chroma_db(dry_run: bool = False) -> bool:
    """
    Clear ChromaDB vector database.
    
    Args:
        dry_run: If True, only print what would be deleted
        
    Returns:
        True if database was cleared
    """
    from config.settings import settings
    
    chroma_dir = Path(settings.CHROMA_PERSIST_DIR)
    
    if chroma_dir.exists():
        if dry_run:
            print(f"  Would delete: {chroma_dir}")
            return True
        else:
            shutil.rmtree(chroma_dir)
            logger.info(f"Cleared ChromaDB: {chroma_dir}")
            return True
    
    return False


def clear_extraction_reports(dry_run: bool = False) -> int:
    """
    Clear extraction report files.
    
    Args:
        dry_run: If True, only print what would be deleted
        
    Returns:
        Number of files removed
    """
    from config.settings import settings
    
    report_dir = Path(settings.EXTRACTION_REPORT_DIR)
    count = 0
    
    if report_dir.exists():
        for item in report_dir.iterdir():
            if item.is_file():
                if dry_run:
                    print(f"  Would delete: {item}")
                else:
                    item.unlink()
                    logger.debug(f"Removed: {item}")
                count += 1
    
    return count


def clear_all_cache(
    include_pycache: bool = True,
    include_app_cache: bool = True,
    include_vectordb: bool = False,
    include_reports: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Clear all caches and temporary files.
    
    Args:
        include_pycache: Clear __pycache__ directories
        include_app_cache: Clear application caches (extraction, embedding, query)
        include_vectordb: Clear vector databases (FAISS, ChromaDB) - DESTRUCTIVE!
        include_reports: Clear extraction reports
        dry_run: If True, only show what would be deleted
        
    Returns:
        Dictionary with cleanup results
        
    Example:
        >>> from src.utils.cleanup import clear_all_cache
        >>> results = clear_all_cache(dry_run=True)  # Preview
        >>> results = clear_all_cache()  # Actually clean
    """
    results = {}
    
    print("=" * 60)
    print("CACHE CLEANUP" + (" (DRY RUN)" if dry_run else ""))
    print("=" * 60)
    
    # 1. Clear __pycache__
    if include_pycache:
        print("\n1. Python Cache (__pycache__):")
        count = clear_pycache(dry_run=dry_run)
        count += clear_pyc_files(dry_run=dry_run)
        results['pycache'] = count
        print(f"   {'Would remove' if dry_run else 'Removed'}: {count} items")
    
    # 2. Clear application caches
    if include_app_cache:
        print("\n2. Application Cache:")
        cache_results = clear_application_cache(dry_run=dry_run)
        results['app_cache'] = cache_results
        for cache_name, count in cache_results.items():
            print(f"   {cache_name}: {count} files")
    
    # 3. Clear vector databases (optional - destructive!)
    if include_vectordb:
        print("\n3. Vector Databases (DESTRUCTIVE!):")
        results['faiss'] = clear_faiss_index(dry_run=dry_run)
        results['chromadb'] = clear_chroma_db(dry_run=dry_run)
        print(f"   FAISS: {'cleared' if results['faiss'] else 'not found'}")
        print(f"   ChromaDB: {'cleared' if results['chromadb'] else 'not found'}")
    
    # 4. Clear extraction reports (optional)
    if include_reports:
        print("\n4. Extraction Reports:")
        count = clear_extraction_reports(dry_run=dry_run)
        results['reports'] = count
        print(f"   {'Would remove' if dry_run else 'Removed'}: {count} files")
    
    print("\n" + "=" * 60)
    if dry_run:
        print("DRY RUN COMPLETE - No files were actually deleted")
    else:
        print("CLEANUP COMPLETE")
    print("=" * 60)
    
    return results


def quick_clean():
    """Quick cleanup of __pycache__ and application caches."""
    return clear_all_cache(
        include_pycache=True,
        include_app_cache=True,
        include_vectordb=False,
        include_reports=False
    )


def full_clean():
    """Full cleanup including vector databases (DESTRUCTIVE!)."""
    return clear_all_cache(
        include_pycache=True,
        include_app_cache=True,
        include_vectordb=True,
        include_reports=True
    )


# CLI entry point
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Clean up cache and temporary files")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Preview what would be deleted")
    parser.add_argument("--all", "-a", action="store_true", help="Clear everything including vectordb")
    parser.add_argument("--pycache", action="store_true", help="Clear __pycache__ only")
    parser.add_argument("--cache", action="store_true", help="Clear application caches only")
    parser.add_argument("--vectordb", action="store_true", help="Clear vector databases (DESTRUCTIVE)")
    parser.add_argument("--reports", action="store_true", help="Clear extraction reports")
    
    args = parser.parse_args()
    
    # Default: clean pycache and app cache
    if not any([args.all, args.pycache, args.cache, args.vectordb, args.reports]):
        clear_all_cache(dry_run=args.dry_run)
    elif args.all:
        full_clean() if not args.dry_run else clear_all_cache(
            include_vectordb=True, include_reports=True, dry_run=True
        )
    else:
        clear_all_cache(
            include_pycache=args.pycache or not any([args.cache, args.vectordb, args.reports]),
            include_app_cache=args.cache or not any([args.pycache, args.vectordb, args.reports]),
            include_vectordb=args.vectordb,
            include_reports=args.reports,
            dry_run=args.dry_run
        )
