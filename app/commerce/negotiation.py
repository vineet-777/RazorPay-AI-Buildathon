"""Structured Agent-Merchant Negotiation Service."""

from typing import List, Optional
from app.commerce.models import NegotiationRequest, NegotiationResponse, Product
from app.commerce.catalog import CatalogService
from app.commerce.merchant_policy import MerchantPolicyService
from app.core.logging import logger


class NegotiationService:
    @staticmethod
    def evaluate_negotiation(req: NegotiationRequest, merchant_id: str) -> NegotiationResponse:
        """Evaluates a structured buyer constraint negotiation against merchant catalog and policy."""
        policy = MerchantPolicyService.get_active_policy(merchant_id)
        if not policy or not policy.ai_sales_enabled:
            return NegotiationResponse(
                eligible=False,
                merchant_id=merchant_id,
                rejection_reason="Merchant AI autonomous commerce is currently disabled."
            )

        # Check if category is allowed by merchant
        if policy.allowed_categories and req.product_category not in policy.allowed_categories:
            return NegotiationResponse(
                eligible=False,
                merchant_id=merchant_id,
                rejection_reason=f"Category '{req.product_category}' is not allowed under merchant policy."
            )

        # Find candidate products
        candidates = CatalogService.list_products(
            category=req.product_category,
            merchant_id=merchant_id,
            max_price=req.hard_ceiling_inr,
            ai_enabled_only=True
        )

        if not candidates:
            # Look for alternatives across all prices for this merchant
            all_alternatives = CatalogService.list_products(
                category=req.product_category,
                merchant_id=merchant_id,
                ai_enabled_only=True
            )
            return NegotiationResponse(
                eligible=False,
                merchant_id=merchant_id,
                rejection_reason=f"No products found under budget ceiling of ₹{req.hard_ceiling_inr:,.2f}.",
                alternatives=all_alternatives[:3]
            )

        # Select best matching candidate (preferred SKU if specified and available, else lowest price matching requirements)
        selected_product: Optional[Product] = None
        if req.preferred_sku:
            for c in candidates:
                if c.sku == req.preferred_sku:
                    selected_product = c
                    break

        if not selected_product:
            # Filter by installation if required
            if req.installation_required:
                install_candidates = [c for c in candidates if c.installation_available]
                selected_product = install_candidates[0] if install_candidates else candidates[0]
            else:
                selected_product = candidates[0]

        # Check inventory
        if selected_product.inventory < req.requested_quantity:
            return NegotiationResponse(
                eligible=False,
                merchant_id=merchant_id,
                sku=selected_product.sku,
                title=selected_product.title,
                original_price_inr=selected_product.price_inr,
                rejection_reason=f"Insufficient inventory (Requested: {req.requested_quantity}, Available: {selected_product.inventory})."
            )

        # Check installation constraint
        installation_included = selected_product.installation_available

        # Calculate negotiated price / discount if applicable
        original_price = selected_product.price_inr * req.requested_quantity
        discount_pct = 0.0
        offered_price = original_price

        if policy.allow_discounts and original_price > req.target_budget_inr:
            # Try to apply merchant policy discount up to max_discount_pct to meet target budget
            diff_needed_pct = ((original_price - req.target_budget_inr) / original_price) * 100.0
            discount_pct = min(diff_needed_pct, policy.max_discount_pct)
            discount_amount = (original_price * discount_pct) / 100.0
            offered_price = round(original_price - discount_amount, 2)

        # Check merchant autonomous ceiling
        if offered_price > policy.max_ai_order_value_inr:
            return NegotiationResponse(
                eligible=False,
                merchant_id=merchant_id,
                sku=selected_product.sku,
                title=selected_product.title,
                original_price_inr=original_price,
                rejection_reason=f"Transaction total ₹{offered_price:,.2f} exceeds merchant autonomous ceiling of ₹{policy.max_ai_order_value_inr:,.2f}."
            )

        return NegotiationResponse(
            eligible=True,
            merchant_id=merchant_id,
            sku=selected_product.sku,
            title=selected_product.title,
            original_price_inr=original_price,
            offered_price_inr=offered_price,
            discount_applied_pct=round(discount_pct, 2),
            delivery_estimate=selected_product.delivery_estimate,
            installation_included=installation_included
        )
