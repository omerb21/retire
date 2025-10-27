#!/usr/bin/env python
"""Clear all Python cache files"""
import shutil
import os

count = 0
for root, dirs, files in os.walk('app'):
    if '__pycache__' in dirs:
        cache_dir = os.path.join(root, '__pycache__')
        print(f"Removing {cache_dir}")
        shutil.rmtree(cache_dir)
        count += 1

print(f"\n✅ Cleared {count} __pycache__ directories")
