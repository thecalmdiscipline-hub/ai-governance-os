import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

os.environ["TESTING"] = "1"

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass
