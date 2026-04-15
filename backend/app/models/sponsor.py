"""
models/sponsor.py — Tracks which products are currently sponsored.
Redis mirrors the active flag for fast badge lookups at render time.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class SponsoredProduct(Base):
    __tablename__ = "sponsored_products"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    product_id: Mapped[str] = mapped_column(
        String(255), index=True, nullable=False
    )
    badge_label: Mapped[str] = mapped_column(
        String(30), nullable=False, default="Sponsored"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    sponsored_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    sponsored_by: Mapped[str] = mapped_column(String(36), nullable=False)  # vendor user_id

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<SponsoredProduct product_id={self.product_id!r}"
            f" until={self.sponsored_until!r}>"
        )

    @property
    def is_currently_sponsored(self) -> bool:
        return self.is_active and datetime.now(timezone.utc) < self.sponsored_until
