from datetime import datetime, timezone
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


class User(Base):
    __tablename__ = "inventory_users"

    username: Mapped[str] = mapped_column(String(64), primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(255))


class LoginSession(Base):
    __tablename__ = "inventory_login_sessions"

    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(ForeignKey("inventory_users.username", ondelete="CASCADE"))
    expires_at: Mapped[int] = mapped_column(BigInteger, index=True)
    user: Mapped[User] = relationship()

MYSQL_TABLE_OPTIONS = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_as_cs"}


class Product(Base):
    __tablename__ = "products"
    __table_args__ = MYSQL_TABLE_OPTIONS

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    supplier: Mapped[str] = mapped_column(String(160))
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    reorder_point: Mapped[int] = mapped_column(Integer, default=0)
    reorder_quantity: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    counts: Mapped[list["PhysicalCount"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class PhysicalCount(Base):
    __tablename__ = "physical_counts"
    __table_args__ = (
        UniqueConstraint("product_id", "event_id", name="uq_product_count_event"),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[str] = mapped_column(String(80), index=True)
    counted_quantity: Mapped[int] = mapped_column(Integer)
    recorded_quantity: Mapped[int] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(Text, default="")
    counted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    product: Mapped[Product] = relationship(back_populates="counts")
