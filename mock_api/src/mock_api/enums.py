"""Value sets used by the order system.

Orders placed before the order system v2 go-live store LegacyOrderStatus values; the API
returns whatever is stored, so clients see both enums.
"""

from enum import StrEnum


class OrderStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELED = "canceled"


class LegacyOrderStatus(StrEnum):
    NEW = "NEW"
    PAID = "PAID"
    INVOICED = "INVOICED"
    PICKING = "PICKING"
    DISPATCHED = "DISPATCHED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class PaymentMethod(StrEnum):
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"


class ShipmentStatus(StrEnum):
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"


class ReturnStatus(StrEnum):
    REQUESTED = "requested"
    APPROVED = "approved"
    RECEIVED = "received"
    REFUNDED = "refunded"
    EXCHANGED = "exchanged"
    REJECTED = "rejected"


class ReturnReason(StrEnum):
    DEFECTIVE = "defective"
    CHANGED_MIND = "changed_mind"
    WRONG_ITEM = "wrong_item"
    DAMAGED_IN_TRANSIT = "damaged_in_transit"


class ReturnResolution(StrEnum):
    REFUND = "refund"
    EXCHANGE = "exchange"


class ItemCondition(StrEnum):
    UNOPENED = "unopened"
    OPENED = "opened"
    DAMAGED = "damaged"


class ReturnSource(StrEnum):
    ADMIN_PANEL = "admin_panel"
    WEB = "web"
    API = "api"
