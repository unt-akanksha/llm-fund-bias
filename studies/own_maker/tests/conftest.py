import sys
from pathlib import Path

# Make studies/own_maker/src and the repo's src/ importable (flat imports, as in the main study).
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
sys.path.insert(1, str(HERE.parents[2] / "src"))
