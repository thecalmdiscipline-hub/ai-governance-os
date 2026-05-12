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


def _disable_login_rate_limit():
    try:
        import app.main as main

        for attr in [
            "check_login_rate_limit",
            "rate_limit_login",
            "enforce_login_rate_limit",
            "login_rate_limit_check",
        ]:
            if hasattr(main, attr):
                setattr(main, attr, lambda *args, **kwargs: None)

        for name in [
            "login_attempts",
            "LOGIN_ATTEMPTS",
            "FAILED_LOGIN_ATTEMPTS",
            "RATE_LIMIT_BUCKETS",
            "login_rate_limit_store",
            "LOGIN_RATE_LIMIT_STORE",
        ]:
            if hasattr(main, name):
                value = getattr(main, name)
                if isinstance(value, dict):
                    value.clear()
    except Exception:
        pass


def pytest_configure(config):
    _disable_login_rate_limit()


def pytest_runtest_setup(item):
    _disable_login_rate_limit()
