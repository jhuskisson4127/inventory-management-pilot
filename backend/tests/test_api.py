import os
from collections import OrderedDict
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

test_directory = TemporaryDirectory()
test_database = (Path(test_directory.name) / "inventory.db").as_posix()
with patch.dict(os.environ, {"DATABASE_URL": f"sqlite:///{test_database}"}):
    from app import auth
    from app.auth import cookie_name, password_hasher
    from app.db import Base, SessionLocal, engine
    from app.main import app
    from app.models import User

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app import main

credentials = {"username": "inventory-test", "password": "test-suite-passphrase"}
write_headers = {"X-Inventory-Request": "1"}
Base.metadata.create_all(engine)
with SessionLocal() as db:
    db.add(User(username=credentials["username"], password_hash=password_hasher.hash(credentials["password"])))
    db.commit()


@pytest.fixture(autouse=True)
def reset_login_attempts(monkeypatch):
    monkeypatch.setattr(auth, "login_attempts", OrderedDict())


@pytest.fixture(scope="module", autouse=True)
def close_test_database():
    yield
    engine.dispose()
    test_directory.cleanup()


@pytest.fixture
def client():
    with TestClient(app, base_url="https://testserver", headers=write_headers) as authenticated:
        assert authenticated.post("/api/auth/login", json=credentials).status_code == 200
        yield authenticated


def test_inventory_routes_require_a_session():
    anonymous = TestClient(app, headers=write_headers)
    for route in app.routes:
        if route.path.startswith("/api/") and not route.path.startswith("/api/auth/"):
            path = route.path.replace("{product_id}", "1")
            for method in route.methods:
                response = anonymous.request(method, path)
                assert response.status_code == 401, (method, path)
                assert response.headers["cache-control"] == "no-store"


def test_login_logout_and_session_replay():
    with TestClient(app, base_url="https://testserver", headers=write_headers) as browser:
        for account in (credentials["username"], "unknown-user"):
            response = browser.post("/api/auth/login", json={"username": account, "password": "incorrect"})
            assert response.status_code == 401
            assert response.json() == {"detail": "Invalid username or password"}
        response = browser.post("/api/auth/login", json=credentials)
        assert response.status_code == 200
        cookie = response.headers["set-cookie"]
        for attribute in ("__Host-inventory_session=", "HttpOnly", "Secure", "SameSite=lax", "Path=/"):
            assert attribute in cookie
        assert credentials["password"] not in response.text
        assert browser.get("/api/auth/session").json() == {"username": credentials["username"]}
        token = browser.cookies.get(cookie_name())
        assert browser.post("/api/auth/logout").status_code == 204
        assert browser.get("/api/products", headers={"Cookie": f"{cookie_name()}={token}"}).status_code == 401


def test_protected_page_redirects_and_cannot_be_reopened_after_logout(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<div id='root'></div>", encoding="utf-8")
    monkeypatch.setattr(main, "static_dir", tmp_path)
    with TestClient(app, base_url="https://testserver", headers=write_headers, follow_redirects=False) as browser:
        for path in ("/", "/inventory", "/sample_inventory.csv"):
            response = browser.get(path)
            assert response.status_code == 303
            assert response.headers["location"] == "/login"
            assert response.headers["cache-control"] == "no-store"
        assert browser.get("/index.html").status_code == 404
        assert browser.get("/login").status_code == 200
        assert browser.post("/api/auth/login", json=credentials).status_code == 200
        page = browser.get("/inventory")
        assert page.status_code == 200
        assert page.headers["cache-control"] == "no-store"
        assert browser.post("/api/auth/logout").status_code == 204
        reopened = browser.get("/inventory", headers={"If-None-Match": page.headers["etag"]})
        assert reopened.status_code == 303
        assert reopened.headers["location"] == "/login"


def test_account_password_is_stored_as_an_argon2id_hash():
    with SessionLocal() as db:
        stored = db.scalar(select(User.password_hash).where(User.username == credentials["username"]))
        assert stored.startswith("$argon2id$")
        assert credentials["password"] not in stored
        assert password_hasher.verify(stored, credentials["password"])


def test_cookie_authenticated_writes_require_csrf_header(client):
    response = client.post("/api/products", headers={"X-Inventory-Request": "0"}, json=product())
    assert response.status_code == 403
    assert client.post("/api/auth/logout", headers={"X-Inventory-Request": "0"}).status_code == 403
    assert client.get("/api/auth/session").status_code == 200


def test_expired_session_is_rejected(client, monkeypatch):
    expires_at = auth.time() + auth.session_seconds + 1
    monkeypatch.setattr(auth, "time", lambda: expires_at)
    assert client.get("/api/auth/session").status_code == 401
    assert client.get("/api/products").status_code == 401


def test_repeated_login_attempts_are_throttled():
    browser = TestClient(app, headers=write_headers)
    wrong_credentials = {"username": credentials["username"], "password": "incorrect"}
    for _ in range(10):
        assert browser.post("/api/auth/login", json=wrong_credentials).status_code == 401
    assert browser.post("/api/auth/login", json=wrong_credentials).status_code == 429


def test_login_validation_does_not_return_submitted_password():
    response = TestClient(app, headers=write_headers).post(
        "/api/auth/login", json={"username": "", "password": "sensitive-test-value"}
    )
    assert response.status_code == 422
    assert "sensitive-test-value" not in response.text

def product(sku="TEST-1",quantity=5,reorder_point=5):
    return {"sku":sku,"name":"Test Item","supplier":"Test Supplier","quantity":quantity,"reorder_point":reorder_point,"reorder_quantity":10}

def test_product_crud_and_quantity(client):
    res=client.post("/api/products",json=product()); assert res.status_code==201
    pid=res.json()["id"]; assert client.get(f"/api/products/{pid}").json()["status"]=="Reorder"
    edited=product("TEST-1",20,5); edited["name"]="Edited Item"
    assert client.put(f"/api/products/{pid}",json=edited).json()["name"]=="Edited Item"
    assert client.patch(f"/api/products/{pid}/quantity",json={"quantity":8}).json()["quantity"]==8
    assert client.delete(f"/api/products/{pid}").status_code==204

def test_reorder_status_recommendations_and_alerts(client):
    for row in [product("ZERO",0,5), product("ZERO-POINT",0,0), product("LOW",4,5),
                product("AT",5,5), product("HIGH",6,5)]:
        assert client.post("/api/products", json=row).status_code == 201
    reorders = {p["sku"]: p["status"] for p in client.get("/api/reorders").json()}
    assert reorders["ZERO"] == reorders["ZERO-POINT"] == "Out of Stock"
    assert reorders.keys() >= {"LOW", "AT"}
    assert {p["sku"] for p in client.get("/api/alerts").json()} >= {"ZERO", "ZERO-POINT", "LOW", "AT"}
    states={p["sku"]:p["status"] for p in client.get("/api/products").json()}
    assert states["ZERO"] == states["ZERO-POINT"] == "Out of Stock"
    assert states["LOW"]==states["AT"]=="Reorder" and states["HIGH"]=="In stock"

def test_manual_entry_csv_import_and_physical_count(client):
    assert client.post("/api/products",json=product("MANUAL")).status_code==201
    with open("sample_inventory.csv","rb") as f: res=client.post("/api/import",files={"file":("sample.csv",f,"text/csv")})
    assert res.status_code==200 and len(res.json())==20
    pid=res.json()[0]["id"]
    count=client.post("/api/counts",json={"product_id":pid,"event_id":"cycle-1","counted_quantity":13,"note":"Shelf count"})
    assert count.status_code==201 and count.json()["discrepancy"]==13-res.json()[0]["quantity"]
    assert client.get("/api/counts").json()[0]["event_id"]=="cycle-1"
