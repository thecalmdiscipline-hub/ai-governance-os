"""
Batch H (2026-10-07): run all 10 fictional demo workflow scenarios (quote_contract_generator
runs twice: an English and a Dutch variant) against a live API, for a fully fictitious demo tenant
(e.g. "Atlas Demo B.V."). Reused later by Batch M (handout generator) and the video production to
get the same set of real, realistic-looking outputs without re-authoring scenarios.

Usage:
    DEMO_TOKEN=<access token of the demo tenant's admin>
    BASE_URL=https://api.valqeron.com          (default http://127.0.0.1:8000)
    python3 scripts/run_demo_scenarios.py --org-name "Atlas Demo B.V."

DEMO_TOKEN comes from the environment; this script never mints a token itself (same convention as
scripts/smoke_provision.sh) — mint one server-side, in memory, and export it just for this command.
Prints, per workflow: workflow_key, status, duration_seconds, run_id. Never prints the workflow's
own output text — only a content check (non-empty, no unresolved <PLACEHOLDER> token). A failing
run is retried once; if still failing it is recorded and the run continues, unless more than two
distinct workflows have each failed twice, in which case the whole run stops (see main()).
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCENARIOS_DIR = Path(__file__).resolve().parent / "data" / "demo-scenarios"

# workflow_key -> HTTP route segment (hyphenated; see app/workflows/routers/*.py).
WORKFLOW_ROUTES = {
    "sales_lead_qualification": "sales-lead-qualification",
    "document_knowledge": "document-knowledge",
    "invoice_processing": "invoice-processing",
    "compliance_monitoring": "compliance-monitoring",
    "customer_support": "customer-support",
    "hr_recruitment": "hr-recruitment",
    "marketing_automation": "marketing-automation",
    "meeting_agenda_assistant": "meeting-agenda-assistant",
    "quote_contract_generator": "quote-contract-generator",
    "business_intelligence": "business-intelligence",
}

_PLACEHOLDER_RE = re.compile(r"<[A-Z][A-Z_-]*(_\d+)?>")


def _call(base_url: str, token: str, route: str, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/workflows/{route}/run",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"error": body}


def _content_problems(output: Dict[str, Any]) -> List[str]:
    """Non-empty, no unresolved placeholder tokens. Does not check text content itself (never
    printed), only structural signals that something clearly went wrong."""
    problems = []
    text = json.dumps(output)
    if not output:
        problems.append("empty output")
    if _PLACEHOLDER_RE.search(text):
        problems.append("unresolved placeholder token found")
    return problems


def run_one(base_url: str, token: str, workflow_key: str, payload: Dict[str, Any], variant: str = "") -> Dict[str, Any]:
    route = WORKFLOW_ROUTES[workflow_key]
    label = f"{workflow_key}{(':' + variant) if variant else ''}"

    for attempt in (1, 2):
        start = time.monotonic()
        status, body = _call(base_url, token, route, {"input": payload})
        duration = round(time.monotonic() - start, 2)

        if status == 200 and body.get("status") == "ok":
            problems = _content_problems(body.get("output", {}))
            if not problems:
                return {
                    "workflow": label,
                    "attempt": attempt,
                    "http_status": status,
                    "run_id": body.get("run_id"),
                    "duration_seconds": duration,
                    "ok": True,
                    "problems": [],
                }
            # Content problem: treat like a failure for retry purposes, but keep the run_id.
            if attempt == 1:
                continue
            return {
                "workflow": label, "attempt": attempt, "http_status": status, "run_id": body.get("run_id"),
                "duration_seconds": duration, "ok": False, "problems": problems,
            }

        if attempt == 1:
            continue
        return {
            "workflow": label, "attempt": attempt, "http_status": status, "run_id": body.get("run_id"),
            "duration_seconds": duration, "ok": False,
            "problems": [f"http_status={status} workflow_status={body.get('status')} error={body.get('error')}"],
        }

    return {"workflow": label, "attempt": 2, "ok": False, "problems": ["unreachable"]}  # pragma: no cover


def load_scenarios() -> List[Tuple[str, Dict[str, Any], Optional[Dict[str, Any]]]]:
    """Returns (workflow_key, input, extra_variant_input_or_None) for every scenario file, in a
    fixed, predictable order (sorted by workflow_key)."""
    out = []
    for path in sorted(SCENARIOS_DIR.glob("*.json")):
        with open(path) as f:
            config = json.load(f)
        workflow_key = config["workflow_key"]
        if workflow_key not in WORKFLOW_ROUTES:
            raise SystemExit(f"{path.name}: unknown workflow_key {workflow_key!r}")
        if not config.get("fictional"):
            raise SystemExit(f"{path.name}: missing or false 'fictional' field — refusing to run")
        out.append((workflow_key, config["input"], config.get("extra_variant")))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--org-name", default="", help="for the report header only; not sent to the API")
    args = parser.parse_args()

    token = os.environ.get("DEMO_TOKEN")
    if not token:
        raise SystemExit("Set DEMO_TOKEN (see the header of this script). This script never mints one.")
    base_url = os.environ.get("BASE_URL", "http://127.0.0.1:8000")

    print(f"org: {args.org_name or '(not given)'}  base_url: {base_url}")

    scenarios = load_scenarios()
    results: List[Dict[str, Any]] = []
    fail_counts: Dict[str, int] = {}

    for workflow_key, payload, extra_variant in scenarios:
        result = run_one(base_url, token, workflow_key, payload)
        results.append(result)
        if not result["ok"]:
            fail_counts[workflow_key] = fail_counts.get(workflow_key, 0) + 1
        print(json.dumps(result))

        if extra_variant is not None:
            result2 = run_one(base_url, token, workflow_key, extra_variant, variant="extra")
            results.append(result2)
            if not result2["ok"]:
                fail_counts[workflow_key] = fail_counts.get(workflow_key, 0) + 1
            print(json.dumps(result2))

        twice_failed = [k for k, n in fail_counts.items() if n >= 2]
        if len(twice_failed) > 2:
            print(f"STOPPING: more than two workflows failed twice in a row: {twice_failed}")
            break

    ok_count = sum(1 for r in results if r["ok"])
    print(f"{ok_count}/{len(results)} runs ok")


if __name__ == "__main__":
    main()
