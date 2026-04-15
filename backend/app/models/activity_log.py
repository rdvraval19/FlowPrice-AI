"""app/models/activity_log.py — Persistent user activity + points ledger.

Each row is an immutable event record — points are never mutated in-place,
they are summed from the ledger. This gives a full audit trail and makes
the points balance 100% replayable from raw data.

Point values (calibrated to purchase funnel depth):
  product_view    →  1 pt   (discovery)
  wishlist_add    →  3 pts  (intent signal)
  cart_add        →  5 pts  (strong intent)
  purchase        → 20 pts  (conversion)
  review_read     →  2 pts  (engagement)
  session_start   →  1 pt   (daily login bonus)

These are defined in LoyaltyEngine so they can be tuned without schema changes.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    # Who did what
    user_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True,
        comment="FK → users.id (not enforced at DB level for performance)",
    )
    session_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True,
    )

    # What happened
    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="Mirrors EventType enum values",
    )
    product_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True,
    )
    category: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
    )
    price_shown: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="USD price shown to user at time of event",
    )

    # Points awarded for this event
    points_awarded: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Points credited to user for this specific event",
    )

    # Extra context (JSON string — avoids schema migration for new fields)
    metadata_json: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="JSON blob for order_id, coupon_used, etc.",
    )

    # When
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<ActivityLog user={self.user_id!r} "
            f"event={self.event_type!r} pts={self.points_awarded}>"
        )
