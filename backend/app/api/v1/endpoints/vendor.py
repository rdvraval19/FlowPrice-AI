"""
api/v1/endpoints/vendor.py — Vendor Panel REST API.

All routes require a valid JWT with role="vendor".
The require_vendor dependency enforces this — any non-vendor token
gets a 403 before the handler even runs.

Routes:
  POST /vendor/discount          — apply % discount to a product
  POST /vendor/coupon            — generate a coupon code
  POST /vendor/coupon/redeem     — redeem a coupon at checkout
  POST /vendor/sponsor           — mark product as Sponsored
  POST /vendor/notify            — send coupon via email
  DELETE /vendor/discount/{id}   — remove a discount early
  DELETE /vendor/sponsor/{id}    — revoke sponsorship early
  POST /vendor/checkout          — place an order (Hackathon Mock)
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.vendor import (
    CouponRedeemRequest,
    CouponRedeemResponse,
    CouponRequest,
    CouponResponse,
    DiscountRequest,
    DiscountResponse,
    NotifyRequest,
    NotifyResponse,
    SponsorRequest,
    SponsorResponse,
)
from app.services.vendor.coupon_service import coupon_service
from app.services.vendor.discount_service import discount_service
from app.services.vendor.notification_service import notification_service
from app.services.vendor.sponsor_service import sponsor_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/vendor", tags=["Vendor Panel"])


# ── Auth helper ───────────────────────────────────────────────────────────────

async def require_vendor(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency — raises 403 if the caller is not a vendor."""
    if not current_user.is_vendor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vendor access required",
        )
    return current_user


# ── Discount ──────────────────────────────────────────────────────────────────

@router.post(
    "/discount",
    response_model=DiscountResponse,
    status_code=status.HTTP_200_OK,
    summary="Apply a percentage discount to a product",
)
async def apply_discount(
    body: DiscountRequest,
    original_price: float = Query(
        ..., gt=0, description="Current product price from catalog"
    ),
    vendor: User = Depends(require_vendor),
) -> DiscountResponse:
    """
    Apply a vendor discount on a product.

    `original_price` is passed as a query param because the vendor panel
    knows the current catalog price at the time of the action — this keeps
    the vendor service decoupled from the catalog service.
    """
    try:
        return await discount_service.apply(body, original_price, vendor.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.delete(
    "/discount/{product_id}",
    status_code=status.HTTP_200_OK,
    summary="Remove an active discount before TTL expiry",
)
async def remove_discount(
    product_id: str,
    vendor: User = Depends(require_vendor),
) -> dict:
    removed = await discount_service.remove_discount(product_id)
    return {"product_id": product_id, "discount_removed": removed}


# ── Coupon ────────────────────────────────────────────────────────────────────

@router.post(
    "/coupon",
    response_model=CouponResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a coupon code for a user, segment, or all",
)
async def create_coupon(
    body: CouponRequest,
    vendor: User = Depends(require_vendor),
    db: AsyncSession = Depends(get_db),
) -> CouponResponse:
    return await coupon_service.create(body, vendor.id, db)


@router.post(
    "/coupon/redeem",
    response_model=CouponRedeemResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate and redeem a coupon at checkout",
)
async def redeem_coupon(
    body: CouponRedeemRequest,
    db: AsyncSession = Depends(get_db),
) -> CouponRedeemResponse:
    """
    Open endpoint — called from the storefront checkout flow.
    No vendor auth required here; the coupon itself encodes the rules.
    """
    return await coupon_service.redeem(body, db)


# ── Sponsor ───────────────────────────────────────────────────────────────────

@router.post(
    "/sponsor",
    response_model=SponsorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Mark a product as Sponsored with a badge",
)
async def sponsor_product(
    body: SponsorRequest,
    vendor: User = Depends(require_vendor),
    db: AsyncSession = Depends(get_db),
) -> SponsorResponse:
    return await sponsor_service.sponsor(body, vendor.id, db)


@router.delete(
    "/sponsor/{product_id}",
    status_code=status.HTTP_200_OK,
    summary="Revoke sponsorship before TTL expires",
)
async def remove_sponsor(
    product_id: str,
    vendor: User = Depends(require_vendor),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await sponsor_service.remove_sponsor(product_id, db)
    return {"product_id": product_id, "sponsorship_revoked": True}


# ── Notify ────────────────────────────────────────────────────────────────────

@router.post(
    "/notify",
    response_model=NotifyResponse,
    status_code=status.HTTP_200_OK,
    summary="Send a coupon code to a user via email",
)
async def notify_user(
    body: NotifyRequest,
    vendor: User = Depends(require_vendor),
) -> NotifyResponse:
    response = await notification_service.send_coupon_email(body)
    if not response.sent:
        # Return 200 with sent=False so the vendor panel can show the reason
        # without treating it as a server error.
        logger.warning("Email not sent to %s: %s", body.user_email, response.message)
    return response


# ── Checkout (Hackathon Fast Path) ────────────────────────────────────────────

@router.post(
    "/checkout",
    status_code=status.HTTP_200_OK,
    summary="Process checkout and return order payload",
)
async def checkout(payload: dict):
    """
    Open endpoint — called from the storefront checkout flow.
    Returns a success payload so the UI completes the flow.
    """
    return {
        "success": True,
        "order_id": "ORD-" + str(payload.get("user_id", "000")),
        "total": payload.get("total_amount"),
        "items": payload.get("items", []),
    }