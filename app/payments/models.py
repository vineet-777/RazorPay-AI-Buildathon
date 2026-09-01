"""Data models for Payments, Transactions, and State Machine."""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
from enum import Enum


class TransactionStatus(str, Enum):
    DRAFT = "DRAFT"
    AUTHORIZATION_PENDING = "AUTHORIZATION_PENDING"
    AUTHORIZED = "AUTHORIZED"
    RESERVED = "RESERVED"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    COMPLETED = "COMPLETED"
    CHALLENGED = "CHALLENGED"
    DENIED = "DENIED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    AUTHORIZATION_EXPIRED = "AUTHORIZATION_EXPIRED"
    AUTHORIZATION_REVOKED = "AUTHORIZATION_REVOKED"
    RESERVATION_RELEASED = "RESERVATION_RELEASED"


class PaymentStatus(str, Enum):
    INITIATED = "INITIATED"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    VERIFIED = "VERIFIED"


class PaymentExecutionRequest(BaseModel):
    transaction_id: str
    decision_id: str
    idempotency_key: str
    simulate_payment_failure: bool = False


class PaymentExecutionResponse(BaseModel):
    success: bool
    transaction_id: str
    decision_id: str
    payment_id: str
    razorpay_order_id: Optional[str] = None
    razorpay_payment_id: Optional[str] = None
    amount_inr: float
    currency: str = "INR"
    status: TransactionStatus
    idempotent_replay: bool = False
    message: str
    signature: Optional[str] = None
