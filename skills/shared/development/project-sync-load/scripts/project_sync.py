#!/usr/bin/env python3
"""Locate the paired save skill; keep a single checkpoint implementation."""
from pathlib import Path
import runpy
import sys

implementation = Path(__file__).resolve().parents[2] / 'project-sync-save' / 'scripts' / 'project_sync.py'
if not implementation.is_file():
    sys.exit('Install project-sync-save and project-sync-load together in the same skills directory.')
runpy.run_path(str(implementation), run_name='__main__')
