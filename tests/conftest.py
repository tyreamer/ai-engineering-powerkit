import os
import tempfile
import pytest
from pathlib import Path
from unittest import mock

@pytest.fixture(autouse=True)
def mock_home():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        original_home = os.environ.get("HOME")
        os.environ["HOME"] = str(temp_path)
        with mock.patch("pathlib.Path.home", return_value=temp_path):
            yield temp_path
        if original_home is not None:
            os.environ["HOME"] = original_home
        else:
            del os.environ["HOME"]
