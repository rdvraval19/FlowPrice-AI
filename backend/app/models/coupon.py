"""
models/coupon.py — Persistent coupon record for audit and history.
Redis holds the hot-path TTL data; this table is the source of truth.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Coupon(Base):
    __tablename__ = "coupons"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    code: Mapped[str] = mapped_column(
        String(20), unique=True, index=True, nullable=False
    )
    discount_pct: Mapped[float] = mapped_column(Float, nullable=False)

    # "all" | "user" | "segment"
    target: Mapped[str] = mapped_column(String(20), nullable=False, default="all")
    target_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    max_uses: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    uses_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)  # vendor user_id

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<Coupon code={self.code!r} discount={self.discount_pct}%"
            f" uses={self.uses_count}/{self.max_uses}>"
        )

    @property
    def uses_remaining(self) -> int:
        return max(0, self.max_uses - self.uses_count)

    @property
    def is_valid(self) -> bool:
        return (
            self.is_active
            and self.uses_remaining > 0
            and datetime.now(timezone.utc) < self.expires_at
        )
