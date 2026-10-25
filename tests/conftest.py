import subprocess
import sys
from pathlib import Path

import pytest

# Make the package importable when running `pytest` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def fake_cp(stdout="", returncode=0, stderr=""):
    return subprocess.CompletedProcess(args=["adb"], returncode=returncode,
                                       stdout=stdout, stderr=stderr)


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    """Point the toolkit root at a temp dir so installs/locks are isolated."""
    monkeypatch.setenv("CYBERHOST_HOME", str(tmp_path))
    return tmp_path
