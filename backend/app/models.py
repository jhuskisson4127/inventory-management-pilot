from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

class Product(Base):
    __tablename__="products"
    id: Mapped[int]=mapped_column(primary_key=True)
    sku: Mapped[str]=mapped_column(String(64),unique=True,index=True)
    name: Mapped[str]=mapped_column(String(160),index=True)
    supplier: Mapped[str]=mapped_column(String(160))
    quantity: Mapped[int]=mapped_column(Integer,default=0)
    reorder_point: Mapped[int]=mapped_column(Integer,default=0)
    reorder_quantity: Mapped[int]=mapped_column(Integer,default=1)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    counts: Mapped[list["PhysicalCount"]]=relationship(back_populates="product",cascade="all, delete-orphan")

class PhysicalCount(Base):
    __tablename__="physical_counts"
    __table_args__=(UniqueConstraint("product_id","event_id",name="uq_product_count_event"),)
    id: Mapped[int]=mapped_column(primary_key=True)
    product_id: Mapped[int]=mapped_column(ForeignKey("products.id",ondelete="CASCADE"),index=True)
    event_id: Mapped[str]=mapped_column(String(80),index=True)
    counted_quantity: Mapped[int]=mapped_column(Integer)
    recorded_quantity: Mapped[int]=mapped_column(Integer)
    note: Mapped[str]=mapped_column(Text,default="")
    counted_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    product: Mapped[Product]=relationship(back_populates="counts")
