import subprocess
import sys
from pathlib import Path


def test_specs_validation_script() -> None:
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([sys.executable, "scripts/check_specs.py"], cwd=root, capture_output=True, text=True, check=True)
    assert "specsmd validation passed" in result.stdout
