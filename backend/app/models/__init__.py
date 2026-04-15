# app/models/__init__.py
# Import all models here so SQLAlchemy's Base.metadata is aware of them
# when init_db calls Base.metadata.create_all().
#
# ORDER MATTERS for foreign-key dependencies — parents before children.
from app.models.user import User                    # noqa: F401
from app.models.activity_log import ActivityLog     # noqa: F401  ← Phase 4

# Phase 3 models (already present)
try:
    from app.models.coupon import Coupon            # noqa: F401
    from app.models.sponsor import Sponsor          # noqa: F401
except ImportError:
    pass  # Phase 3 not yet applied — safe to skip

__all__ = ["User", "ActivityLog", "Coupon", "Sponsor"]