import csv, io
from pathlib import Path
from fastapi import APIRouter, Depends, FastAPI, HTTPException, UploadFile, File
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .db import Base, engine, get_db
from .auth import require_csrf_header, require_user, router as auth_router
from .models import Product, PhysicalCount
from .schemas import ProductIn, ProductOut, QuantityIn, CountIn, CountOut
from .settings import settings

app=FastAPI(title="Inventory Management API",version="1.0.0",description="Local-first inventory tracking and reorder recommendations.")
inventory = APIRouter(dependencies=[Depends(require_user), Depends(require_csrf_header)])
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")
                   if origin.strip().startswith(("http://", "https://"))],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def redact_login_validation(request, exc):
    if request.url.path == "/api/auth/login":
        return JSONResponse({"detail": "Enter a valid username and password"}, status_code=422)
    return await request_validation_exception_handler(request, exc)


@app.middleware("http")
async def prevent_api_caching(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

def output(p):
    values={k:getattr(p,k) for k in ("id","sku","name","supplier","quantity","reorder_point","reorder_quantity","created_at")}
    values["status"]="Reorder" if p.quantity<=p.reorder_point else "In stock"
    return ProductOut(**values)

@app.get("/health")
def health(): return {"status":"ok"}

@inventory.get("/api/products",response_model=list[ProductOut])
def list_products(db:Session=Depends(get_db)):
    return [output(p) for p in db.scalars(select(Product).order_by(Product.name)).all()]

@inventory.post("/api/products",response_model=ProductOut,status_code=201)
def create_product(data:ProductIn,db:Session=Depends(get_db)):
    p=Product(**data.model_dump()); db.add(p)
    try: db.commit()
    except IntegrityError: db.rollback(); raise HTTPException(409,"SKU already exists")
    db.refresh(p); return output(p)

@inventory.get("/api/products/{product_id}",response_model=ProductOut)
def get_product(product_id:int,db:Session=Depends(get_db)):
    p=db.get(Product,product_id)
    if not p: raise HTTPException(404,"Product not found")
    return output(p)

@inventory.put("/api/products/{product_id}",response_model=ProductOut)
def edit_product(product_id:int,data:ProductIn,db:Session=Depends(get_db)):
    p=db.get(Product,product_id)
    if not p: raise HTTPException(404,"Product not found")
    for k,v in data.model_dump().items(): setattr(p,k,v)
    try: db.commit()
    except IntegrityError: db.rollback(); raise HTTPException(409,"SKU already exists")
    db.refresh(p); return output(p)

@inventory.delete("/api/products/{product_id}",status_code=204)
def delete_product(product_id:int,db:Session=Depends(get_db)):
    p=db.get(Product,product_id)
    if not p: raise HTTPException(404,"Product not found")
    db.delete(p); db.commit()

@inventory.patch("/api/products/{product_id}/quantity",response_model=ProductOut)
def update_quantity(product_id:int,data:QuantityIn,db:Session=Depends(get_db)):
    p=db.get(Product,product_id)
    if not p: raise HTTPException(404,"Product not found")
    p.quantity=data.quantity; db.commit(); db.refresh(p); return output(p)

@inventory.get("/api/reorders",response_model=list[ProductOut])
def reorders(db:Session=Depends(get_db)):
    return [output(p) for p in db.scalars(select(Product).where(Product.quantity<=Product.reorder_point).order_by(Product.quantity)).all()]

@inventory.get("/api/alerts")
def alerts(db:Session=Depends(get_db)):
    rows=db.scalars(select(Product).where(Product.quantity<=Product.reorder_point).order_by(Product.name)).all()
    return [{"product_id":p.id,"sku":p.sku,"name":p.name,"quantity":p.quantity,"reorder_point":p.reorder_point,"message":f"{p.name} is at or below its reorder point"} for p in rows]

@inventory.post("/api/import",response_model=list[ProductOut])
def import_csv(file:UploadFile=File(...),db:Session=Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith(".csv"): raise HTTPException(400,"Upload a CSV file")
    try:
        reader=csv.DictReader(io.StringIO(file.file.read().decode("utf-8-sig")))
        required={"sku","name","supplier","quantity","reorder_point","reorder_quantity"}
        if not reader.fieldnames or not required.issubset({x.strip().lower() for x in reader.fieldnames}): raise ValueError("CSV needs columns: "+", ".join(sorted(required)))
        saved=[]
        for row in reader:
            values={k.strip().lower():(v or "").strip() for k,v in row.items() if k}
            data=ProductIn(**values); p=db.scalar(select(Product).where(Product.sku==data.sku))
            if p:
                for k,v in data.model_dump().items(): setattr(p,k,v)
            else: p=Product(**data.model_dump()); db.add(p)
            saved.append(p)
        db.commit()
        for p in saved: db.refresh(p)
        return [output(p) for p in saved]
    except (UnicodeDecodeError,ValueError,TypeError) as exc:
        db.rollback(); raise HTTPException(422,str(exc)) from exc
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(409,"Import contains duplicate SKUs") from exc

@inventory.post("/api/counts",response_model=CountOut,status_code=201)
def record_count(data:CountIn,db:Session=Depends(get_db)):
    p=db.get(Product,data.product_id)
    if not p: raise HTTPException(404,"Product not found")
    c=PhysicalCount(product_id=p.id,event_id=data.event_id,counted_quantity=data.counted_quantity,recorded_quantity=p.quantity,note=data.note); db.add(c)
    try: db.commit()
    except IntegrityError: db.rollback(); raise HTTPException(409,"This product already has a count in that event")
    db.refresh(c)
    return CountOut(id=c.id,product_id=p.id,product_name=p.name,sku=p.sku,event_id=c.event_id,counted_quantity=c.counted_quantity,recorded_quantity=c.recorded_quantity,discrepancy=c.counted_quantity-c.recorded_quantity,note=c.note,counted_at=c.counted_at)

@inventory.get("/api/counts",response_model=list[CountOut])
def list_counts(db:Session=Depends(get_db)):
    return [CountOut(id=c.id,product_id=c.product_id,product_name=c.product.name,sku=c.product.sku,event_id=c.event_id,counted_quantity=c.counted_quantity,recorded_quantity=c.recorded_quantity,discrepancy=c.counted_quantity-c.recorded_quantity,note=c.note,counted_at=c.counted_at) for c in db.scalars(select(PhysicalCount).order_by(PhysicalCount.counted_at.desc())).all()]

app.include_router(auth_router)
app.include_router(inventory)

# In the production container, serve the compiled React app and API from one HTTPS origin.
if Path(settings.static_dir).is_dir():
    app.mount("/",StaticFiles(directory=settings.static_dir,html=True),name="frontend")
