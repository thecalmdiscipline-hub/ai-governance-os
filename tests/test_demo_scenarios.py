"""Batch H (2026-10-07): scripts/run_demo_scenarios.py and the fictional demo-scenario files it
reads. Two things are checked: the scenario files themselves are well-formed fictional data (no
real-looking domain, every email uses .invalid, every workflow_key is a real, existing workflow),
and the script's own run/retry logic behaves correctly against a mocked HTTP layer (never a real
network call, never OpenAI)."""
import importlib
import json
import re
from unittest.mock import patch

import pytest

from app.services.module_access import BASE_MODULES

run_demo = importlib.import_module("scripts.run_demo_scenarios")

_REAL_WORKFLOW_KEYS = {m["workflow_key"] for m in BASE_MODULES if m.get("workflow_key")}

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]+)")


def _all_scenario_configs():
    configs = []
    for path in sorted(run_demo.SCENARIOS_DIR.glob("*.json")):
        with open(path) as f:
            configs.append((path.name, json.load(f)))
    return configs


def test_at_least_ten_scenario_files_exist():
    configs = _all_scenario_configs()
    assert len(configs) >= 10


def test_every_scenario_file_is_marked_fictional():
    for name, config in _all_scenario_configs():
        assert config.get("fictional") is True, f"{name} is missing fictional: true"


def test_every_scenario_workflow_key_matches_a_real_workflow():
    seen = set()
    for name, config in _all_scenario_configs():
        workflow_key = config.get("workflow_key")
        assert workflow_key in _REAL_WORKFLOW_KEYS, f"{name}: unknown workflow_key {workflow_key!r}"
        assert workflow_key in run_demo.WORKFLOW_ROUTES
        seen.add(workflow_key)
    assert seen == _REAL_WORKFLOW_KEYS


def test_every_email_address_uses_the_invalid_tld():
    for name, config in _all_scenario_configs():
        text = json.dumps(config)
        for match in _EMAIL_RE.finditer(text):
            domain = match.group(1)
            assert domain.endswith(".invalid"), f"{name}: email domain {domain!r} is not .invalid"


def test_every_website_field_uses_the_invalid_tld():
    for name, config in _all_scenario_configs():
        text = json.dumps(config)
        for match in re.finditer(r"https?://([A-Za-z0-9.-]+)", text):
            domain = match.group(1)
            assert domain.endswith(".invalid"), f"{name}: URL domain {domain!r} is not .invalid"


def test_quote_contract_generator_has_an_extra_dutch_variant():
    configs = dict(_all_scenario_configs())
    qcg = configs["quote_contract_generator.json"]
    assert qcg["input"]["output_language"] == "en"
    assert qcg["extra_variant"]["output_language"] == "nl"


def _mock_call_factory(responses):
    """responses: dict workflow_route -> list of (status, body) to return in call order."""
    call_log = []

    def _fake_call(base_url, token, route, payload):
        call_log.append(route)
        queue = responses[route]
        return queue.pop(0)

    return _fake_call, call_log


def test_run_one_succeeds_on_first_attempt():
    fake_call, _ = _mock_call_factory({
        "sales-lead-qualification": [(200, {"status": "ok", "run_id": "abc-1", "output": {"score": 70}})],
    })
    with patch.object(run_demo, "_call", fake_call):
        result = run_demo.run_one("http://x", "tok", "sales_lead_qualification", {"lead": {}})
    assert result["ok"] is True
    assert result["attempt"] == 1
    assert result["run_id"] == "abc-1"
    assert result["problems"] == []


def test_run_one_retries_once_then_succeeds():
    fake_call, call_log = _mock_call_factory({
        "sales-lead-qualification": [
            (500, {"status": "error", "error": "boom"}),
            (200, {"status": "ok", "run_id": "abc-2", "output": {"score": 70}}),
        ],
    })
    with patch.object(run_demo, "_call", fake_call):
        result = run_demo.run_one("http://x", "tok", "sales_lead_qualification", {"lead": {}})
    assert result["ok"] is True
    assert result["attempt"] == 2
    assert len(call_log) == 2


def test_run_one_fails_after_two_attempts():
    fake_call, call_log = _mock_call_factory({
        "sales-lead-qualification": [
            (500, {"status": "error", "error": "boom"}),
            (500, {"status": "error", "error": "boom again"}),
        ],
    })
    with patch.object(run_demo, "_call", fake_call):
        result = run_demo.run_one("http://x", "tok", "sales_lead_qualification", {"lead": {}})
    assert result["ok"] is False
    assert result["attempt"] == 2
    assert len(call_log) == 2


def test_run_one_treats_unresolved_placeholder_as_a_failure_worth_retrying():
    fake_call, call_log = _mock_call_factory({
        "sales-lead-qualification": [
            (200, {"status": "ok", "run_id": "abc-3", "output": {"summary": "Hello <LOCATIE>"}}),
            (200, {"status": "ok", "run_id": "abc-4", "output": {"summary": "Hello Sheffield"}}),
        ],
    })
    with patch.object(run_demo, "_call", fake_call):
        result = run_demo.run_one("http://x", "tok", "sales_lead_qualification", {"lead": {}})
    assert result["ok"] is True
    assert result["run_id"] == "abc-4"
    assert len(call_log) == 2


def test_content_problems_flags_empty_output_and_placeholders():
    assert run_demo._content_problems({}) == ["empty output"]
    assert "unresolved placeholder token found" in run_demo._content_problems({"summary": "Hi <ORGANISATIE>"})
    assert run_demo._content_problems({"summary": "all good"}) == []


def test_load_scenarios_returns_every_file_with_the_quote_extra_variant():
    scenarios = run_demo.load_scenarios()
    keys = [s[0] for s in scenarios]
    assert len(keys) == len(set(keys)), "duplicate workflow_key across scenario files"
    assert set(keys) == _REAL_WORKFLOW_KEYS
    qcg = [s for s in scenarios if s[0] == "quote_contract_generator"][0]
    assert qcg[2] is not None, "quote_contract_generator should carry an extra_variant"


def test_load_scenarios_refuses_a_non_fictional_file(tmp_path, monkeypatch):
    bad = tmp_path / "zzz_not_fictional.json"
    bad.write_text(json.dumps({"workflow_key": "sales_lead_qualification", "input": {}}))
    monkeypatch.setattr(run_demo, "SCENARIOS_DIR", tmp_path)
    with pytest.raises(SystemExit):
        run_demo.load_scenarios()
