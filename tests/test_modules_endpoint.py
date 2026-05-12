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


def test_modules_endpoint_returns_org_specific_modules():
    admin_token = login("dennis_admin", "Admin123!")
    customer2_token = login("customer2_admin", "Customer123!")

    admin_res = client.get(
        "/modules",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    customer2_res = client.get(
        "/modules",
        headers={"Authorization": f"Bearer {customer2_token}"},
    )

    assert admin_res.status_code == 200
    assert customer2_res.status_code == 200

    admin_modules = {item["key"]: item["active"] for item in admin_res.json()}
    customer2_modules = {item["key"]: item["active"] for item in customer2_res.json()}

    assert admin_modules["core"] is True
    assert admin_modules["document_intelligence"] is True
    assert admin_modules["customer_support_ai"] is False

    assert customer2_modules["core"] is True
    assert customer2_modules["customer_support_ai"] is True
    assert customer2_modules["document_intelligence"] is False
