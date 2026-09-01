"""Autonomous AI Buyer Agent Workflow."""

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.commerce.catalog import CatalogService
from app.commerce.models import Product, NegotiationRequest
from app.commerce.negotiation import NegotiationService
from app.authorization.models import (
    AgentProposal, CanonicalTransaction, AuthorizationDecision, DecisionEnum
)
from app.authorization.engine import AuthorizationFirewall
from app.payments.models import PaymentExecutionRequest, PaymentExecutionResponse
from app.payments.razorpay_client import RazorpayGatewayService
from app.core.logging import logger


class ShoppingTaskRequest(BaseModel):
    user_id: str
    contract_id: str
    goal: str
    target_budget_inr: Optional[float] = None
    hard_ceiling_inr: Optional[float] = None
    preferred_category: Optional[str] = None
    destination_pincode: Optional[str] = "560001"
    installation_required: bool = False
    requested_quantity: int = 1
    execute_payment_if_allowed: bool = True


class ShoppingTaskResult(BaseModel):
    task_id: str
    goal: str
    extracted_constraints: Dict[str, Any]
    discovered_candidates_count: int
    selected_product: Optional[Product] = None
    proposal: Optional[AgentProposal] = None
    canonical_transaction: Optional[CanonicalTransaction] = None
    authorization_decision: Optional[AuthorizationDecision] = None
    payment_response: Optional[PaymentExecutionResponse] = None
    status: str
    summary_message: str


class BuyerAgent:
    """Autonomous AI Buyer that discovers merchant offers, negotiates terms, and submits canonical transactions."""

    @classmethod
    def execute_shopping_task(cls, req: ShoppingTaskRequest) -> ShoppingTaskResult:
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        logger.info(f"AI Buyer starting shopping task {task_id} for user '{req.user_id}': '{req.goal}'")

        # 1. Parse and extract structured shopping constraints
        constraints = cls._extract_constraints(req)

        # 2. Discover matching products across machine-readable merchant catalogs
        candidates = CatalogService.list_products(
            category=constraints["category"],
            max_price=constraints["hard_ceiling_inr"],
            ai_enabled_only=True
        )

        if not candidates:
            return ShoppingTaskResult(
                task_id=task_id,
                goal=req.goal,
                extracted_constraints=constraints,
                discovered_candidates_count=0,
                status="NO_PRODUCTS_FOUND",
                summary_message=f"No matching products found under ceiling of ₹{constraints['hard_ceiling_inr']:,.2f} in category '{constraints['category']}'."
            )

        # 3. Rank candidates based on user preferences (installation, budget, delivery speed)
        selected_product = cls._rank_and_select(candidates, constraints)
        if not selected_product:
            selected_product = candidates[0]

        # 4. Negotiate terms with merchant if necessary
        neg_req = NegotiationRequest(
            product_category=selected_product.category,
            preferred_sku=selected_product.sku,
            target_budget_inr=constraints["target_budget_inr"],
            hard_ceiling_inr=constraints["hard_ceiling_inr"],
            delivery_pincode=constraints["destination_pincode"],
            installation_required=constraints["installation_required"],
            requested_quantity=constraints["requested_quantity"]
        )
        neg_resp = NegotiationService.evaluate_negotiation(neg_req, selected_product.merchant_id)

        final_price = neg_resp.offered_price_inr if (neg_resp.eligible and neg_resp.offered_price_inr) else (selected_product.price_inr * req.requested_quantity)
        subtotal = round(selected_product.price_inr * req.requested_quantity, 2)
        discount = round(subtotal - final_price, 2) if subtotal > final_price else 0.0
        tax = round(final_price * 0.05, 2)  # 5% GST on groceries/electronics demo
        shipping = 0.0 if final_price > 1000.0 else 50.0  # Free shipping over ₹1000
        total_inr = round(final_price + tax + shipping, 2)

        # 5. Form Agent Proposal (declared intent)
        proposal = AgentProposal(
            sku=selected_product.sku,
            title=selected_product.title,
            merchant_id=selected_product.merchant_id,
            category=selected_product.category,
            unit_price_inr=selected_product.price_inr,
            quantity=req.requested_quantity,
            estimated_total_inr=total_inr,
            currency="INR",
            destination_pincode=constraints["destination_pincode"],
            recurring=False
        )

        # 6. Construct Canonical Executable Transaction
        tx_id = f"tx_{uuid.uuid4().hex[:10]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        canonical_tx = CanonicalTransaction(
            transaction_id=tx_id,
            principal_id=req.user_id,
            agent_id="buyer_agent_01",
            merchant_id=selected_product.merchant_id,
            sku=selected_product.sku,
            category=selected_product.category,
            quantity=req.requested_quantity,
            unit_price_inr=selected_product.price_inr,
            subtotal_inr=subtotal,
            discount_inr=discount,
            tax_inr=tax,
            shipping_inr=shipping,
            total_inr=total_inr,
            currency="INR",
            destination_pincode=constraints["destination_pincode"],
            recurring=False,
            timestamp=now_iso,
            contract_id=req.contract_id,
            idempotency_key=f"idem_{tx_id}"
        )

        # 7. Submit to Deterministic Authorization Firewall
        decision = AuthorizationFirewall.evaluate(
            tx=canonical_tx,
            proposal=proposal
        )

        # 8. Trigger Razorpay Test-Mode Payment if ALLOWED
        payment_resp = None
        if decision.decision == DecisionEnum.ALLOW and req.execute_payment_if_allowed:
            pay_req = PaymentExecutionRequest(
                transaction_id=tx_id,
                decision_id=decision.decision_id,
                idempotency_key=canonical_tx.idempotency_key or f"idem_{tx_id}"
            )
            payment_resp = RazorpayGatewayService.execute_payment(pay_req)

        status_msg = f"Task completed: Decision {decision.decision.value}."
        if payment_resp and payment_resp.success:
            status_msg += f" Razorpay payment successful (Order: {payment_resp.razorpay_order_id})."

        return ShoppingTaskResult(
            task_id=task_id,
            goal=req.goal,
            extracted_constraints=constraints,
            discovered_candidates_count=len(candidates),
            selected_product=selected_product,
            proposal=proposal,
            canonical_transaction=canonical_tx,
            authorization_decision=decision,
            payment_response=payment_resp,
            status=decision.decision.value,
            summary_message=status_msg
        )

    @classmethod
    def _extract_constraints(cls, req: ShoppingTaskRequest) -> Dict[str, Any]:
        lower = req.goal.lower()

        # Category
        category = req.preferred_category
        if not category:
            if any(w in lower for w in ["tv", "television", "sony", "lg", "screen", "headphone"]):
                category = "electronics"
            elif any(w in lower for w in ["grocer", "oat", "milk", "oil", "food", "pantry"]):
                category = "groceries"
            elif any(w in lower for w in ["skincare", "sunscreen", "cleanser"]):
                category = "personal_care"
            else:
                category = "groceries"

        # Budgets
        target = req.target_budget_inr or 70000.0 if category == "electronics" else 2000.0
        ceiling = req.hard_ceiling_inr or 75000.0 if category == "electronics" else 5000.0

        # Installation
        installation = req.installation_required or ("installation" in lower or "install" in lower)

        return {
            "category": category,
            "target_budget_inr": target,
            "hard_ceiling_inr": ceiling,
            "installation_required": installation,
            "destination_pincode": req.destination_pincode or "560001",
            "requested_quantity": req.requested_quantity
        }

    @classmethod
    def _rank_and_select(cls, candidates: List[Product], constraints: Dict[str, Any]) -> Optional[Product]:
        if constraints["installation_required"]:
            install_matches = [c for c in candidates if c.installation_available]
            if install_matches:
                return install_matches[0]
        return candidates[0] if candidates else None
