# Import all models so Alembic and Base.metadata see them.
from app.models.asset import Asset, AssetType  # noqa: F401
from app.models.feedback import Feedback, FeedbackType  # noqa: F401
from app.models.finding import DamageSeverity, Finding, FindingStatus  # noqa: F401
from app.models.inspection import Inspection, InspectionStatus, InspectionType  # noqa: F401
from app.models.model_metrics import ModelMetrics  # noqa: F401
from app.models.photo import Photo  # noqa: F401
from app.models.rental_session import RentalSession, RentalSessionStatus  # noqa: F401
from app.models.repair_cost import RepairCostLookup  # noqa: F401
from app.models.tenant import Tenant  # noqa: F401
from app.models.user import User, UserRole  # noqa: F401
