import os
os.environ.setdefault("DATABASE_URL","sqlite:///./test_inventory.db")
from fastapi.testclient import TestClient
from app.db import Base, engine
from app.main import app

Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
client=TestClient(app)

def product(sku="TEST-1",quantity=5,reorder_point=5):
    return {"sku":sku,"name":"Test Item","supplier":"Test Supplier","quantity":quantity,"reorder_point":reorder_point,"reorder_quantity":10}

def test_product_crud_and_quantity():
    res=client.post("/api/products",json=product()); assert res.status_code==201
    pid=res.json()["id"]; assert client.get(f"/api/products/{pid}").json()["status"]=="Reorder"
    edited=product("TEST-1",20,5); edited["name"]="Edited Item"
    assert client.put(f"/api/products/{pid}",json=edited).json()["name"]=="Edited Item"
    assert client.patch(f"/api/products/{pid}/quantity",json={"quantity":8}).json()["quantity"]==8
    assert client.delete(f"/api/products/{pid}").status_code==204

def test_reorder_status_recommendations_and_alerts():
    for row in [product("LOW",4,5),product("AT",5,5),product("HIGH",6,5)]: client.post("/api/products",json=row)
    assert {p["sku"] for p in client.get("/api/reorders").json()} >= {"LOW","AT"}
    assert {p["sku"] for p in client.get("/api/alerts").json()} >= {"LOW","AT"}
    states={p["sku"]:p["status"] for p in client.get("/api/products").json()}
    assert states["LOW"]==states["AT"]=="Reorder" and states["HIGH"]=="In stock"

def test_manual_entry_csv_import_and_physical_count():
    assert client.post("/api/products",json=product("MANUAL")).status_code==201
    with open("sample_inventory.csv","rb") as f: res=client.post("/api/import",files={"file":("sample.csv",f,"text/csv")})
    assert res.status_code==200 and len(res.json())==2
    pid=res.json()[0]["id"]
    count=client.post("/api/counts",json={"product_id":pid,"event_id":"cycle-1","counted_quantity":13,"note":"Shelf count"})
    assert count.status_code==201 and count.json()["discrepancy"]==-2
    assert client.get("/api/counts").json()[0]["event_id"]=="cycle-1"
