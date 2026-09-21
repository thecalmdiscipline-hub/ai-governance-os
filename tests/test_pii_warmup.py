"""Startup warm-up switch (PII_WARMUP_ON_STARTUP) — see app/main.py lifespan."""
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core import pii_anonymizer
from app.main import app


def test_warmup_off_by_default_loads_nothing(monkeypatch):
    monkeypatch.delenv("PII_WARMUP_ON_STARTUP", raising=False)
    warm = MagicMock()
    monkeypatch.setattr(pii_anonymizer, "warm_up", warm)
    with TestClient(app):
        pass
    warm.assert_not_called()


@pytest.mark.parametrize("value", ["", "0", "false", "off"])
def test_warmup_falsy_values_load_nothing(monkeypatch, value):
    monkeypatch.setenv("PII_WARMUP_ON_STARTUP", value)
    warm = MagicMock()
    monkeypatch.setattr(pii_anonymizer, "warm_up", warm)
    with TestClient(app):
        pass
    warm.assert_not_called()


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "on"])
def test_warmup_on_calls_init_exactly_once(monkeypatch, value):
    monkeypatch.setenv("PII_WARMUP_ON_STARTUP", value)
    warm = MagicMock(return_value=True)
    monkeypatch.setattr(pii_anonymizer, "warm_up", warm)
    with TestClient(app):
        pass
    warm.assert_called_once_with()


def test_warm_up_failure_logs_error_and_does_not_raise(monkeypatch, caplog):
    def boom():
        raise RuntimeError("models missing")

    monkeypatch.setattr(pii_anonymizer, "_get_engines", boom)
    with caplog.at_level("ERROR", logger=pii_anonymizer.logger.name):
        assert pii_anonymizer.warm_up() is False
    assert "warm-up failed" in caplog.text


def test_app_still_starts_when_warm_up_fails(monkeypatch):
    monkeypatch.setenv("PII_WARMUP_ON_STARTUP", "1")
    monkeypatch.setattr(pii_anonymizer, "_get_engines", MagicMock(side_effect=RuntimeError("x")))
    with TestClient(app) as client:
        assert client.get("/health").status_code in (200, 503)


def test_warm_up_pre_imports_openai(monkeypatch):
    import sys

    monkeypatch.setattr(pii_anonymizer, "_get_engines", MagicMock())
    monkeypatch.setattr(pii_anonymizer, "anonymize_text", MagicMock())
    monkeypatch.delitem(sys.modules, "openai", raising=False)
    assert pii_anonymizer.warm_up() is True
    assert "openai" in sys.modules  # imported during the warm-up, not in the first request


def test_warm_up_survives_a_failing_openai_import(monkeypatch, caplog):
    import sys

    monkeypatch.setattr(pii_anonymizer, "_get_engines", MagicMock())
    monkeypatch.setattr(pii_anonymizer, "anonymize_text", MagicMock())
    monkeypatch.setitem(sys.modules, "openai", None)  # `import openai` now raises ImportError
    with caplog.at_level("WARNING", logger=pii_anonymizer.logger.name):
        assert pii_anonymizer.warm_up() is True  # the PII part still counts as a successful warm-up
    assert "openai pre-import failed" in caplog.text
