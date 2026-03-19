from fastapi.testclient import TestClient
from app.main import app

def test_workflow_routes_present_in_openapi():
    client = TestClient(app)
    spec = client.get("/openapi.json").json()
    paths = spec.get("paths", {})

    expected = [
        "/workflows/customer-support/run",
        "/workflows/document-knowledge/run",
        "/workflows/sales-lead-qualification/run",
        "/workflows/quote-contract-generator/run",
        "/workflows/meeting-agenda-assistant/run",
        "/workflows/marketing-automation/run",
        "/workflows/invoice-processing/run",
        "/workflows/compliance-monitoring/run",
        "/workflows/hr-recruitment/run",
        "/workflows/business-intelligence/run",
    ]

    missing = [p for p in expected if p not in paths]
    assert not missing, f"Missing workflow paths: {missing}"
