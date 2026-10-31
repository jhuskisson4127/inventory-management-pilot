from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class ProductIn(BaseModel):
    sku: str=Field(min_length=1,max_length=64)
    name: str=Field(min_length=1,max_length=160)
    supplier: str=Field(min_length=1,max_length=160)
    quantity: int=Field(ge=0)
    reorder_point: int=Field(ge=0)
    reorder_quantity: int=Field(default=1,ge=1)
class QuantityIn(BaseModel): quantity: int=Field(ge=0)
class ProductOut(ProductIn):
    id: int
    status: str
    created_at: datetime
    model_config=ConfigDict(from_attributes=True)
class CountIn(BaseModel):
    product_id: int
    event_id: str=Field(min_length=1,max_length=80)
    counted_quantity: int=Field(ge=0)
    note: str=Field(default="",max_length=1000)
class CountOut(BaseModel):
    id:int; product_id:int; product_name:str; sku:str; event_id:str
    counted_quantity:int; recorded_quantity:int; discrepancy:int; note:str; counted_at:datetime
