"""Data models for Commerce, Merchant Catalog, and Policies."""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime


class Product(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sku: str = Field(..., description="Unique product Stock Keeping Unit")
    merchant_id: str = Field(..., description="Merchant identifier")
    title: str = Field(..., description="Product title")
    description: Optional[str] = None
    category: str = Field(..., description="Category (groceries, electronics, personal_care, home_appliances)")
    price_inr: float = Field(..., ge=0, description="Price in INR")
    currency: str = Field(default="INR")
    inventory: int = Field(default=0, ge=0, description="Available stock quantity")
    delivery_estimate: str = Field(..., description="Delivery estimate e.g. '1-2 days'")
    installation_available: bool = Field(default=False)
    substitution_allowed: bool = Field(default=False)
    recurring_allowed: bool = Field(default=False)
    ai_enabled: bool = Field(default=True, description="Whether product can be purchased autonomously by AI")
    specs: Optional[Dict[str, Any]] = Field(default_factory=dict)


class Merchant(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    merchant_id: str
    name: str
    category: str
    is_verified: bool = True
    created_at: str


class MerchantPolicy(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    merchant_id: str
    version: str = Field(..., description="Policy version string e.g. 'v1', 'v14', 'v15'")
    ai_sales_enabled: bool = True
    max_ai_order_value_inr: float = Field(..., ge=0, description="Maximum single transaction order amount permitted for autonomous AI")
    allowed_categories: List[str] = Field(default_factory=list)
    allow_quantity_changes: bool = True
    allow_substitutions: bool = False
    allow_discounts: bool = True
    max_discount_pct: float = Field(default=10.0, ge=0, le=100)
    require_step_up_rules: List[str] = Field(
        default_factory=lambda: ["new_customer", "high_value_order", "product_substitution", "address_drift"]
    )
    is_active: bool = True
    created_at: Optional[str] = None


class NegotiationRequest(BaseModel):
    product_category: str
    preferred_sku: Optional[str] = None
    target_budget_inr: float
    hard_ceiling_inr: float
    delivery_deadline: Optional[str] = None
    delivery_pincode: Optional[str] = None
    installation_required: bool = False
    requested_quantity: int = 1


class NegotiationResponse(BaseModel):
    eligible: bool
    merchant_id: str
    sku: Optional[str] = None
    title: Optional[str] = None
    original_price_inr: Optional[float] = None
    offered_price_inr: Optional[float] = None
    discount_applied_pct: float = 0.0
    delivery_estimate: Optional[str] = None
    installation_included: bool = False
    rejection_reason: Optional[str] = None
    alternatives: List[Product] = Field(default_factory=list)
