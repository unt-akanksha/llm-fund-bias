import sys
from pathlib import Path

# Make src/ importable (scripts use flat imports like `from common import ...`).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
