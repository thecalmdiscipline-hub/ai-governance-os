from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def login(username: str, password: str) -> str:
    res = client.post(
        "/login",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res.status_code == 200
    return res.json()["access_token"]


def test_customer2_sees_only_own_documents_and_workflows():
    admin_token = login("dennis_admin", "Admin123!")
    customer2_token = login("customer2_admin", "Customer123!")

    upload_res = client.post(
        "/documents/upload",
        headers={"Authorization": f"Bearer {customer2_token}"},
        files={"file": ("customer2_isolation.txt", b"customer2 private content", "text/plain")},
    )
    assert upload_res.status_code == 200

    customer2_docs = client.get(
        "/documents",
        headers={"Authorization": f"Bearer {customer2_token}"},
    )
    assert customer2_docs.status_code == 200
    customer2_items = customer2_docs.json()["items"]
    assert any(item["filename"] == "customer2_isolation.txt" for item in customer2_items)

    admin_docs = client.get(
        "/documents",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_docs.status_code == 200
    admin_items = admin_docs.json()["items"]
    assert all(item["filename"] != "customer2_isolation.txt" for item in admin_items)

    run_res = client.post(
        "/workflows/customer-support/run",
        headers={"Authorization": f"Bearer {customer2_token}"},
        json={
            "input": {"issue": "customer2 isolation workflow", "priority": "high"},
            "context": {},
        },
    )
    assert run_res.status_code == 200
    run_id = run_res.json()["run_id"]

    customer2_history = client.get(
        "/workflows/history?limit=20",
        headers={"Authorization": f"Bearer {customer2_token}"},
    )
    assert customer2_history.status_code == 200
    customer2_runs = customer2_history.json()["items"]
    assert any(item["run_id"] == run_id for item in customer2_runs)

    admin_history = client.get(
        "/workflows/history?limit=20",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_history.status_code == 200
    admin_runs = admin_history.json()["items"]
    assert all(item["run_id"] != run_id for item in admin_runs)
