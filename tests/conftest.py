import os

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def datadir():
    return Path(os.path.dirname(__file__), "data")
