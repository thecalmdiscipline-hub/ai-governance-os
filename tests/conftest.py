import os
import sys
from pathlib import Path

# Zorg dat "app" importeerbaar is: voeg repo-root toe aan PYTHONPATH
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# Laad .env indien aanwezig (handig voor OPENAI_API_KEY tests)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass
