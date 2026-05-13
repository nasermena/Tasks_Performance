"""
Pytest configuration for the TasksPerformance test suite.

Adds the project root to sys.path so that `config`, `cfg_store`,
and `sheets_backend` can be imported from the tests/ sub-directory.
Also resets all module-level state in sheets_backend before every test.
"""

import sys
from pathlib import Path

# Ensure the project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import sheets_backend


@pytest.fixture(autouse=True)
def _reset_sheets_backend_state():
    """Wipe module-level globals in sheets_backend before (and after) each test."""
    def _clear():
        sheets_backend.RUNTIME_SHEET_ID = None
        sheets_backend.RUNTIME_WORKSHEET_TITLE = None
        sheets_backend._WS = None
        sheets_backend._TASK_IDS = None

    _clear()
    yield
    _clear()
