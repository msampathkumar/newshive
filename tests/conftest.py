import pytest
import sqlite_utils
from pathlib import Path
import tempfile

@pytest.fixture
def temp_db_path():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        yield Path(f.name)

@pytest.fixture
def temp_data_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)
