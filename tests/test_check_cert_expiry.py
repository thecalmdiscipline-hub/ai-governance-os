"""Batch R3 (2026-10-07): scripts/check_cert_expiry.py — the TLS handshake itself is mocked in
every test here (get_cert_not_after is monkeypatched); no real network call happens."""
import datetime
import importlib

import pytest

cert_check = importlib.import_module("scripts.check_cert_expiry")


def _days_from_now(days: int) -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)


def test_domain_with_plenty_of_days_is_ok(monkeypatch):
    monkeypatch.setattr(cert_check, "get_cert_not_after", lambda hostname, **kwargs: _days_from_now(60))
    result = cert_check.check_domain("example.invalid")
    assert result["ok"] is True
    assert result["error"] is None
    assert result["days_remaining"] >= 59  # allow for the test's own small timing slack


def test_domain_almost_expired_is_not_ok(monkeypatch):
    monkeypatch.setattr(cert_check, "get_cert_not_after", lambda hostname, **kwargs: _days_from_now(5))
    result = cert_check.check_domain("example.invalid")
    assert result["ok"] is False
    assert result["error"] is None
    assert result["days_remaining"] <= 5


def test_domain_exactly_at_the_threshold_is_ok(monkeypatch):
    # A small safety margin (+1 hour) keeps this deterministic: check_domain() recomputes "now" a
    # few milliseconds after this fake notAfter is built, and days_remaining floors — exactly 21
    # days with no margin can floor to 20 purely from that elapsed time, which is not the
    # boundary behavior this test means to check.
    not_after = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=21, hours=1)
    monkeypatch.setattr(cert_check, "get_cert_not_after", lambda hostname, **kwargs: not_after)
    result = cert_check.check_domain("example.invalid", warning_days=21)
    assert result["ok"] is True
    assert result["days_remaining"] == 21


def test_failed_handshake_reports_an_error_not_a_days_count(monkeypatch):
    def _raise(hostname, **kwargs):
        raise OSError("Connection refused")

    monkeypatch.setattr(cert_check, "get_cert_not_after", _raise)
    result = cert_check.check_domain("example.invalid")
    assert result["ok"] is False
    assert result["days_remaining"] is None
    assert "Connection refused" in result["error"]


def test_main_exit_code_0_when_every_domain_is_fine(monkeypatch, capsys):
    monkeypatch.setattr(cert_check, "get_cert_not_after", lambda hostname, **kwargs: _days_from_now(60))
    exit_code = cert_check.main(["a.invalid", "b.invalid"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "a.invalid" in out and "b.invalid" in out


def test_main_exit_code_1_when_one_domain_is_almost_expired(monkeypatch):
    def _fake(hostname, **kwargs):
        return _days_from_now(5) if hostname == "expiring.invalid" else _days_from_now(60)

    monkeypatch.setattr(cert_check, "get_cert_not_after", _fake)
    exit_code = cert_check.main(["fine.invalid", "expiring.invalid"])
    assert exit_code == 1


def test_main_exit_code_1_when_a_handshake_fails(monkeypatch):
    def _fake(hostname, **kwargs):
        if hostname == "unreachable.invalid":
            raise OSError("timed out")
        return _days_from_now(60)

    monkeypatch.setattr(cert_check, "get_cert_not_after", _fake)
    exit_code = cert_check.main(["fine.invalid", "unreachable.invalid"])
    assert exit_code == 1


def test_get_cert_not_after_is_never_called_by_check_domain_more_than_once(monkeypatch):
    calls = []
    monkeypatch.setattr(cert_check, "get_cert_not_after", lambda hostname, **kwargs: (calls.append(hostname), _days_from_now(60))[1])
    cert_check.check_domain("once.invalid")
    assert calls == ["once.invalid"]
