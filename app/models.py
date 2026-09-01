import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column, String, DateTime, Integer, Float, Boolean, Text, ForeignKey, Enum, Index, UniqueConstraint
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


def generate_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    authorizations = relationship("UserAuthorization", back_populates="user")
    budget_reservations = relationship("BudgetReservation", back_populates="user")


class Agent(Base):
    __tablename__ = "agents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    type = Column(String(50), default="buyer")
    config = Column(JSON, default={})
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    authorizations = relationship("UserAuthorization", back_populates="agent")


class Merchant(Base):
    __tablename__ = "merchants"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    ai_commerce_enabled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    products = relationship("Product", back_populates="merchant")
    policies = relationship("MerchantPolicy", back_populates="merchant")
    transactions = relationship("Transaction", back_populates="merchant")


class Product(Base):
    __tablename__ = "products"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    merchant_id = Column(String(36), ForeignKey("merchants.id"), nullable=False, index=True)
    sku = Column(String(100), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=False, index=True)
    price_inr = Column(Integer, nullable=False)
    currency = Column(String(3), default="INR")
    inventory = Column(Integer, default=0)
    delivery_estimate_days = Column(Integer, default=3)
    substitution_allowed = Column(Boolean, default=False)
    installation_available = Column(Boolean, default=False)
    recurring_available = Column(Boolean, default=False)
    ai_commerce_eligible = Column(Boolean, default=True)
    metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    merchant = relationship("Merchant", back_populates="products")

    __table_args__ = (
        UniqueConstraint("merchant_id", "sku", name="uq_merchant_sku"),
        Index("ix_product_merchant_category", "merchant_id", "category"),
    )


class UserAuthorizationStatus(str, enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    PENDING = "pending"


class UserAuthorization(Base):
    __tablename__ = "user_authorizations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    agent_id = Column(String(36), ForeignKey("agents.id"), nullable=False, index=True)
    contract_id = Column(String(100), unique=True, nullable=False, index=True)
    version = Column(Integer, default=1)

    merchants_allowlist = Column(JSON, default=[])
    categories_allowlist = Column(JSON, default=[])
    max_order_value_inr = Column(Integer, nullable=False)
    max_aggregate_value_inr = Column(Integer, nullable=False)
    budget_period_days = Column(Integer, default=7)
    recurring_purchase_allowed = Column(Boolean, default=False)
    delivery_pincodes = Column(JSON, default=[])
    approval_conditions = Column(JSON, default=[])

    issued_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    revocation_version = Column(Integer, default=0)
    status = Column(Enum(UserAuthorizationStatus), default=UserAuthorizationStatus.ACTIVE, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="authorizations")
    agent = relationship("Agent", back_populates="authorizations")
    budget_reservations = relationship("BudgetReservation", back_populates="authorization")

    __table_args__ = (
        Index("ix_auth_user_agent_active", "user_id", "agent_id", "status"),
    )


class MerchantPolicyStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class MerchantPolicy(Base):
    __tablename__ = "merchant_policies"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    merchant_id = Column(String(36), ForeignKey("merchants.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)

    ai_sales_enabled = Column(Boolean, default=True)
    max_ai_order_value_inr = Column(Integer, default=10000)
    allowed_categories = Column(JSON, default=[])
    allowed_regions = Column(JSON, default=[])
    allow_quantity_changes = Column(Boolean, default=True)
    allow_substitutions = Column(Boolean, default=False)
    allow_discounts = Column(Boolean, default=True)
    max_ai_discount_percent = Column(Integer, default=10)
    recurring_purchases_allowed = Column(Boolean, default=False)
    new_customer_approval = Column(String(20), default="challenge")
    high_value_approval_threshold_inr = Column(Integer, default=5000)
    high_value_approval = Column(String(20), default="challenge")
    step_up_rules = Column(JSON, default=[])
    metadata = Column(JSON, default={})

    status = Column(Enum(MerchantPolicyStatus), default=MerchantPolicyStatus.ACTIVE, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    activated_at = Column(DateTime, nullable=True)
    archived_at = Column(DateTime, nullable=True)

    merchant = relationship("Merchant", back_populates="policies")

    __table_args__ = (
        UniqueConstraint("merchant_id", "version", name="uq_merchant_policy_version"),
        Index("ix_policy_merchant_active", "merchant_id", "status"),
    )


class TransactionStatus(str, enum.Enum):
    DRAFT = "draft"
    AUTHORIZATION_PENDING = "authorization_pending"
    AUTHORIZED = "authorized"
    CHALLENGED = "challenged"
    DENIED = "denied"
    PAYMENT_PENDING = "payment_pending"
    PAYMENT_SUCCESS = "payment_success"
    PAYMENT_FAILED = "payment_failed"
    COMPLETED = "completed"
    AUTHORIZATION_EXPIRED = "authorization_expired"
    AUTHORIZATION_REVOKED = "authorization_revoked"
    RESERVATION_RELEASED = "reservation_released"


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    decision_id = Column(String(36), unique=True, nullable=False, index=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    agent_id = Column(String(36), ForeignKey("agents.id"), nullable=False, index=True)
    merchant_id = Column(String(36), ForeignKey("merchants.id"), nullable=False, index=True)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False)
    authorization_id = Column(String(36), ForeignKey("user_authorizations.id"), nullable=True)
    merchant_policy_version = Column(Integer, nullable=True)

    sku = Column(String(100), nullable=False)
    category = Column(String(100), nullable=False)
    quantity = Column(Integer, default=1)
    unit_price_inr = Column(Integer, nullable=False)
    subtotal_inr = Column(Integer, nullable=False)
    discount_inr = Column(Integer, default=0)
    tax_inr = Column(Integer, default=0)
    shipping_inr = Column(Integer, default=0)
    total_inr = Column(Integer, nullable=False)
    currency = Column(String(3), default="INR")
    destination_pincode = Column(String(10), nullable=True)
    recurring = Column(Boolean, default=False)

    status = Column(Enum(TransactionStatus), default=TransactionStatus.DRAFT, nullable=False, index=True)
    idempotency_key = Column(String(100), unique=True, nullable=True, index=True)

    razorpay_order_id = Column(String(100), nullable=True)
    razorpay_payment_id = Column(String(100), nullable=True)
    razorpay_signature = Column(String(255), nullable=True)

    authorized_at = Column(DateTime, nullable=True)
    payment_initiated_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    merchant = relationship("Merchant", back_populates="transactions")
    authorization_decision = relationship("AuthorizationDecision", back_populates="transaction", uselist=False)
    budget_reservation = relationship("BudgetReservation", back_populates="transaction", uselist=False)
    events = relationship("TransactionEvent", back_populates="transaction")


class AuthorizationDecision(Base):
    __tablename__ = "authorization_decisions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    transaction_id = Column(String(36), ForeignKey("transactions.id"), unique=True, nullable=False, index=True)
    decision_id = Column(String(36), unique=True, nullable=False, index=True, default=generate_uuid)

    decision = Column(String(20), nullable=False)
    reason_code = Column(String(100), nullable=True)
    matched_rules = Column(JSON, default=[])
    failed_rules = Column(JSON, default=[])
    user_policy_version = Column(Integer, nullable=True)
    merchant_policy_version = Column(Integer, nullable=True)
    budget_state = Column(JSON, default={})
    risk_checks = Column(JSON, default={})
    evaluated_transaction = Column(JSON, default={})

    evaluated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    transaction = relationship("Transaction", back_populates="authorization_decision")


class BudgetReservationStatus(str, enum.Enum):
    PENDING = "pending"
    RESERVED = "reserved"
    COMMITTED = "committed"
    RELEASED = "released"
    EXPIRED = "expired"


class BudgetReservation(Base):
    __tablename__ = "budget_reservations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    authorization_id = Column(String(36), ForeignKey("user_authorizations.id"), nullable=False, index=True)
    transaction_id = Column(String(36), ForeignKey("transactions.id"), unique=True, nullable=True, index=True)

    amount_inr = Column(Integer, nullable=False)
    status = Column(Enum(BudgetReservationStatus), default=BudgetReservationStatus.PENDING, nullable=False)
    reserved_at = Column(DateTime, nullable=True)
    committed_at = Column(DateTime, nullable=True)
    released_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="budget_reservations")
    authorization = relationship("UserAuthorization", back_populates="budget_reservations")
    transaction = relationship("Transaction", back_populates="budget_reservation")


class AuditEventType(str, enum.Enum):
    AUTHORIZATION_REQUEST = "authorization_request"
    AUTHORIZATION_DECISION = "authorization_decision"
    BUDGET_RESERVATION = "budget_reservation"
    BUDGET_COMMIT = "budget_commit"
    BUDGET_RELEASE = "budget_release"
    PAYMENT_INITIATED = "payment_initiated"
    PAYMENT_SUCCESS = "payment_success"
    PAYMENT_FAILED = "payment_failed"
    POLICY_CREATED = "policy_created"
    POLICY_UPDATED = "policy_updated"
    POLICY_ARCHIVED = "policy_archived"
    AUTHORIZATION_CREATED = "authorization_created"
    AUTHORIZATION_REVOKED = "authorization_revoked"
    TRANSACTION_MUTATION_DETECTED = "transaction_mutation_detected"
    PROMPT_INJECTION_ATTEMPT = "prompt_injection_attempt"
    REPLAY_EVALUATION = "replay_evaluation"


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    event_type = Column(Enum(AuditEventType), nullable=False, index=True)
    correlation_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    merchant_id = Column(String(36), ForeignKey("merchants.id"), nullable=True, index=True)
    transaction_id = Column(String(36), ForeignKey("transactions.id"), nullable=True, index=True)
    decision_id = Column(String(36), nullable=True, index=True)

    payload = Column(JSON, default={})
    previous_hash = Column(String(64), nullable=True)
    current_hash = Column(String(64), nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        Index("ix_audit_correlation_created", "correlation_id", "created_at"),
    )