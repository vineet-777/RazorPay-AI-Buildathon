from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from enum import Enum


class UserAuthorizationStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    PENDING = "pending"


class MerchantPolicyStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class TransactionStatus(str, Enum):
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


class BudgetReservationStatus(str, Enum):
    PENDING = "pending"
    RESERVED = "reserved"
    COMMITTED = "committed"
    RELEASED = "released"
    EXPIRED = "expired"


class AuthorizationDecisionType(str, Enum):
    ALLOW = "ALLOW"
    CHALLENGE = "CHALLENGE"
    DENY = "DENY"


class AuditEventType(str, Enum):
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


class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str = Field(min_length=8)


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentCreate(BaseModel):
    name: str
    type: str = "buyer"
    config: Dict[str, Any] = {}


class AgentResponse(BaseModel):
    id: str
    name: str
    type: str
    config: Dict[str, Any]
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MerchantCreate(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=8)


class MerchantResponse(BaseModel):
    id: str
    name: str
    email: str
    is_active: bool
    ai_commerce_enabled: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    category: str = Field(min_length=1, max_length=100)
    price_inr: int = Field(gt=0)
    currency: str = "INR"
    inventory: int = Field(ge=0, default=0)
    delivery_estimate_days: int = Field(ge=0, default=3)
    substitution_allowed: bool = False
    installation_available: bool = False
    recurring_available: bool = False
    ai_commerce_eligible: bool = True
    metadata: Dict[str, Any] = {}


class ProductUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = Field(default=None, max_length=100)
    price_inr: Optional[int] = Field(default=None, gt=0)
    inventory: Optional[int] = Field(default=None, ge=0)
    delivery_estimate_days: Optional[int] = Field(default=None, ge=0)
    substitution_allowed: Optional[bool] = None
    installation_available: Optional[bool] = None
    recurring_available: Optional[bool] = None
    ai_commerce_eligible: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None


class ProductResponse(BaseModel):
    id: str
    merchant_id: str
    sku: str
    title: str
    description: Optional[str]
    category: str
    price_inr: int
    currency: str
    inventory: int
    delivery_estimate_days: int
    substitution_allowed: bool
    installation_available: bool
    recurring_available: bool
    ai_commerce_eligible: bool
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductSearchRequest(BaseModel):
    category: Optional[str] = None
    max_price_inr: Optional[int] = None
    min_price_inr: Optional[int] = None
    merchant_id: Optional[str] = None
    query: Optional[str] = None
    in_stock_only: bool = True
    ai_commerce_only: bool = True
    limit: int = Field(default=20, le=100)
    offset: int = Field(default=0, ge=0)


class ProductSearchResponse(BaseModel):
    products: List[ProductResponse]
    total: int
    limit: int
    offset: int


class UserAuthorizationCreate(BaseModel):
    agent_id: str
    merchants_allowlist: List[str] = []
    categories_allowlist: List[str] = []
    max_order_value_inr: int = Field(gt=0)
    max_aggregate_value_inr: int = Field(gt=0)
    budget_period_days: int = Field(default=7, gt=0)
    recurring_purchase_allowed: bool = False
    delivery_pincodes: List[str] = []
    approval_conditions: List[str] = []
    expires_in_days: int = Field(default=7, gt=0)


class UserAuthorizationResponse(BaseModel):
    id: str
    user_id: str
    agent_id: str
    contract_id: str
    version: int
    merchants_allowlist: List[str]
    categories_allowlist: List[str]
    max_order_value_inr: int
    max_aggregate_value_inr: int
    budget_period_days: int
    recurring_purchase_allowed: bool
    delivery_pincodes: List[str]
    approval_conditions: List[str]
    issued_at: datetime
    expires_at: datetime
    revoked_at: Optional[datetime]
    revocation_version: int
    status: UserAuthorizationStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MerchantPolicyCreate(BaseModel):
    ai_sales_enabled: bool = True
    max_ai_order_value_inr: int = Field(default=10000, gt=0)
    allowed_categories: List[str] = []
    allowed_regions: List[str] = []
    allow_quantity_changes: bool = True
    allow_substitutions: bool = False
    allow_discounts: bool = True
    max_ai_discount_percent: int = Field(default=10, ge=0, le=100)
    recurring_purchases_allowed: bool = False
    new_customer_approval: Literal["allow", "challenge", "deny"] = "challenge"
    high_value_approval_threshold_inr: int = Field(default=5000, gt=0)
    high_value_approval: Literal["allow", "challenge", "deny"] = "challenge"
    step_up_rules: List[Dict[str, Any]] = []
    metadata: Dict[str, Any] = {}


class MerchantPolicyResponse(BaseModel):
    id: str
    merchant_id: str
    version: int
    ai_sales_enabled: bool
    max_ai_order_value_inr: int
    allowed_categories: List[str]
    allowed_regions: List[str]
    allow_quantity_changes: bool
    allow_substitutions: bool
    allow_discounts: bool
    max_ai_discount_percent: int
    recurring_purchases_allowed: bool
    new_customer_approval: str
    high_value_approval_threshold_inr: int
    high_value_approval: str
    step_up_rules: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    status: MerchantPolicyStatus
    created_at: datetime
    activated_at: Optional[datetime]
    archived_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class CanonicalTransaction(BaseModel):
    decision_id: str
    user_id: str
    agent_id: str
    merchant_id: str
    product_id: str
    sku: str
    category: str
    quantity: int = Field(gt=0)
    unit_price_inr: int = Field(gt=0)
    subtotal_inr: int = Field(gt=0)
    discount_inr: int = Field(ge=0, default=0)
    tax_inr: int = Field(ge=0, default=0)
    shipping_inr: int = Field(ge=0, default=0)
    total_inr: int = Field(gt=0)
    currency: str = "INR"
    destination_pincode: Optional[str] = None
    recurring: bool = False
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    authorization_version: Optional[int] = None
    merchant_policy_version: Optional[int] = None
    idempotency_key: Optional[str] = None


class TransactionCreate(BaseModel):
    product_id: str
    quantity: int = Field(default=1, gt=0)
    destination_pincode: Optional[str] = None
    idempotency_key: Optional[str] = None


class TransactionResponse(BaseModel):
    id: str
    decision_id: str
    user_id: str
    agent_id: str
    merchant_id: str
    product_id: str
    sku: str
    category: str
    quantity: int
    unit_price_inr: int
    subtotal_inr: int
    discount_inr: int
    tax_inr: int
    shipping_inr: int
    total_inr: int
    currency: str
    destination_pincode: Optional[str]
    recurring: bool
    status: TransactionStatus
    razorpay_order_id: Optional[str]
    razorpay_payment_id: Optional[str]
    authorized_at: Optional[datetime]
    payment_initiated_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuthorizationDecisionResponse(BaseModel):
    id: str
    transaction_id: str
    decision_id: str
    decision: AuthorizationDecisionType
    reason_code: Optional[str]
    matched_rules: List[str]
    failed_rules: List[str]
    user_policy_version: Optional[int]
    merchant_policy_version: Optional[int]
    budget_state: Dict[str, Any]
    risk_checks: Dict[str, Any]
    evaluated_transaction: Dict[str, Any]
    evaluated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BudgetReservationResponse(BaseModel):
    id: str
    user_id: str
    authorization_id: str
    transaction_id: Optional[str]
    amount_inr: int
    status: BudgetReservationStatus
    reserved_at: Optional[datetime]
    committed_at: Optional[datetime]
    released_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RazorpayOrderCreate(BaseModel):
    amount_inr: int = Field(gt=0)
    currency: str = "INR"
    receipt: Optional[str] = None
    notes: Dict[str, str] = {}


class RazorpayOrderResponse(BaseModel):
    id: str
    entity: str
    amount: int
    amount_paid: int
    amount_due: int
    currency: str
    receipt: Optional[str]
    status: str
    created_at: int


class RazorpayPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class RazorpayPaymentResponse(BaseModel):
    success: bool
    payment_id: Optional[str] = None
    order_id: Optional[str] = None
    message: Optional[str] = None


class DecisionTraceResponse(BaseModel):
    decision_id: str
    transaction_id: str
    user_delegation: UserAuthorizationResponse
    agent_proposal: Dict[str, Any]
    product_snapshot: ProductResponse
    canonical_transaction: CanonicalTransaction
    merchant_policy: MerchantPolicyResponse
    authorization_decision: AuthorizationDecisionResponse
    budget_reservation: Optional[BudgetReservationResponse]
    payment_result: Optional[RazorpayPaymentResponse]
    audit_events: List[Dict[str, Any]]


class ReplayRequest(BaseModel):
    decision_id: str
    policy_version: Optional[int] = None


class ReplayResponse(BaseModel):
    original_decision: AuthorizationDecisionResponse
    replayed_decision: AuthorizationDecisionResponse
    policy_version_used: int
    differences: List[str]


class AdversarialTestCase(BaseModel):
    id: str
    name: str
    category: str
    description: str
    input_transaction: CanonicalTransaction
    expected_decision: AuthorizationDecisionType
    expected_reason_code: Optional[str] = None


class AdversarialTestResult(BaseModel):
    test_id: str
    name: str
    category: str
    passed: bool
    expected_decision: AuthorizationDecisionType
    actual_decision: AuthorizationDecisionType
    expected_reason_code: Optional[str]
    actual_reason_code: Optional[str]
    latency_ms: float
    details: Dict[str, Any]


class AdversarialSuiteResult(BaseModel):
    total_tests: int
    passed: int
    failed: int
    false_allow_rate: float
    false_deny_rate: float
    challenge_rate: float
    avg_latency_ms: float
    p95_latency_ms: float
    results: List[AdversarialTestResult]


class PolicyCompilerRequest(BaseModel):
    natural_language: str
    user_id: str
    agent_id: str


class PolicyCompilerResponse(BaseModel):
    proposed_contract: UserAuthorizationCreate
    ambiguities: List[Dict[str, Any]]
    requires_confirmation: bool
    confirmation_questions: List[str]


class BuyerAgentRequest(BaseModel):
    user_id: str
    agent_id: str
    shopping_goal: str
    constraints: Optional[Dict[str, Any]] = None


class BuyerAgentResponse(BaseModel):
    proposal: Optional[CanonicalTransaction]
    recommended_products: List[ProductResponse]
    reasoning: str
    requires_approval: bool
    approval_reasons: List[str]