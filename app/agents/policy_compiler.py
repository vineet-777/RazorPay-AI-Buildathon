"""Natural-Language Policy Compiler with Ambiguity Detection."""

import re
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field
from app.authorization.contracts import UserAuthorizationContract, ContractService
from app.core.config import settings
from app.core.logging import logger


class PolicyCompilationRequest(BaseModel):
    principal_id: str
    agent_id: str = "buyer_agent_01"
    natural_language_prompt: str
    confirmed_ambiguities: Optional[Dict[str, Any]] = None


class AmbiguityItem(BaseModel):
    field: str
    question: str
    options: List[str]
    default_assumption: str
    risk_level: str  # "HIGH", "MEDIUM", "LOW"


class PolicyCompilationResult(BaseModel):
    success: bool
    requires_confirmation: bool
    ambiguities: List[AmbiguityItem] = Field(default_factory=list)
    contract_candidate: Optional[UserAuthorizationContract] = None
    explanation: str


class PolicyCompiler:
    """Compiles natural language delegation into structured, versioned authorization contracts."""

    @classmethod
    def compile(cls, req: PolicyCompilationRequest) -> PolicyCompilationResult:
        prompt = req.natural_language_prompt.strip()
        logger.info(f"Compiling natural-language policy for user '{req.principal_id}': '{prompt}'")

        # Extract limits and entities using deterministic NLP parsing
        parsed = cls._parse_delegation(prompt)
        ambiguities = cls._detect_ambiguities(prompt, parsed, req.confirmed_ambiguities)

        # If high risk ambiguities exist and are not confirmed, require user confirmation
        high_risk_ambiguities = [a for a in ambiguities if a.risk_level == "HIGH"]
        if high_risk_ambiguities and not req.confirmed_ambiguities:
            return PolicyCompilationResult(
                success=True,
                requires_confirmation=True,
                ambiguities=ambiguities,
                contract_candidate=None,
                explanation="The delegation contains important ambiguities that require your explicit confirmation before money authority can be activated."
            )

        # Build confirmed contract
        now = datetime.now(timezone.utc)
        valid_days = parsed.get("valid_days", 7)
        expires = now + timedelta(days=valid_days)

        # Merge confirmed ambiguity choices
        confirmed = req.confirmed_ambiguities or {}
        single_cap = confirmed.get("max_order_value_inr", parsed["max_order_value_inr"])
        agg_cap = confirmed.get("max_aggregate_value_inr", parsed["max_aggregate_value_inr"])
        recurring_ok = confirmed.get("recurring_allowed", parsed["recurring_allowed"])
        categories = confirmed.get("categories_allowlist", parsed["categories_allowlist"])
        merchants = confirmed.get("merchants_allowlist", parsed["merchants_allowlist"])
        pincodes = confirmed.get("delivery_pincodes", parsed["delivery_pincodes"])

        contract_id = f"contract_gen_{uuid.uuid4().hex[:8]}"

        contract = UserAuthorizationContract(
            contract_id=contract_id,
            principal_id=req.principal_id,
            agent_id=req.agent_id,
            version=1,
            merchants_allowlist=merchants,
            categories_allowlist=categories,
            max_order_value_inr=float(single_cap),
            max_aggregate_value_inr=float(agg_cap),
            budget_period=parsed.get("budget_period", "weekly"),
            recurring_allowed=bool(recurring_ok),
            delivery_pincodes=pincodes,
            approval_conditions=["new_merchant", "price_increase_over_10_percent", "substituted_sku", "unapproved_pincode"],
            issued_at=now.isoformat(),
            expires_at=expires.isoformat(),
            is_revoked=False,
            raw_natural_language=prompt
        )

        return PolicyCompilationResult(
            success=True,
            requires_confirmation=False,
            ambiguities=ambiguities,
            contract_candidate=contract,
            explanation=f"Compiled machine-checkable policy contract. Maximum order: ₹{contract.max_order_value_inr:,.2f}, Aggregate {contract.budget_period} limit: ₹{contract.max_aggregate_value_inr:,.2f}."
        )

    @classmethod
    def _parse_delegation(cls, text: str) -> Dict[str, Any]:
        lower = text.lower()

        # Find amounts (e.g. ₹5,000, 5000 inr, 70k, 75000)
        amounts: List[float] = []
        # Match ₹ patterns e.g. ₹5,000 or Rs. 5000 or 5000 inr
        raw_amounts = re.findall(r'(?:₹|rs\.?|inr)?\s*([0-9]+(?:,[0-9]+)*(?:\.[0-9]+)?|\d+k)\s*(?:inr|rs)?', lower)
        for ra in raw_amounts:
            ra_clean = ra.replace(",", "").strip()
            if not ra_clean:
                continue
            if ra_clean.endswith("k"):
                try:
                    amounts.append(float(ra_clean[:-1]) * 1000.0)
                except ValueError:
                    pass
            else:
                try:
                    val = float(ra_clean)
                    if val > 50:  # Ignore trivial numbers like 65 inch TV
                        amounts.append(val)
                except ValueError:
                    pass

        # Sort amounts ascending
        amounts = sorted(list(set(amounts)))

        single_order_cap = 2500.0
        agg_budget = 5000.0

        if len(amounts) == 1:
            # If only one amount specified, check context
            if "total" in lower or "week" in lower or "month" in lower or "budget" in lower:
                agg_budget = amounts[0]
                single_order_cap = amounts[0] if ("order" in lower or "single" in lower) else round(amounts[0] / 2, 2)
            else:
                single_order_cap = amounts[0]
                agg_budget = amounts[0]
        elif len(amounts) >= 2:
            single_order_cap = amounts[0]
            agg_budget = amounts[-1]

        # Detect categories
        categories = []
        if any(w in lower for w in ["grocer", "food", "pantry", "vegetable", "fruit", "milk", "oat", "oil"]):
            categories.append("groceries")
        if any(w in lower for w in ["tv", "television", "electronic", "headphone", "gadget", "laptop", "phone"]):
            categories.append("electronics")
        if any(w in lower for w in ["skincare", "cream", "lotion", "sunscreen", "cleanser", "personal care", "wellness"]):
            categories.append("personal_care")
        if any(w in lower for w in ["appliance", "fridge", "microwave", "washing machine"]):
            categories.append("home_appliances")

        if not categories:
            categories = ["groceries", "personal_care", "electronics"]

        # Detect merchants
        merchants = []
        if "freshmart" in lower:
            merchants.append("merchant_freshmart")
        if "croma" in lower:
            merchants.append("merchant_croma_store")
        if "quickdash" in lower or "quick" in lower:
            merchants.append("merchant_quickdash")
        if "apothecary" in lower or "apollo" in lower:
            merchants.append("merchant_apothecary")

        if not merchants:
            # Default to verified trusted merchant pool
            merchants = ["merchant_freshmart", "merchant_croma_store", "merchant_apothecary", "merchant_quickdash"]

        # Detect period
        period = "weekly"
        valid_days = 7
        if "month" in lower:
            period = "monthly"
            valid_days = 30
        elif "day" in lower or "today" in lower:
            period = "daily"
            valid_days = 1
        elif "order" in lower or "once" in lower or "tv" in lower:
            period = "per_order"
            valid_days = 14

        # Recurring
        recurring = False
        if "recurring" in lower or "subscription" in lower or "every week" in lower or "monthly delivery" in lower:
            if "no recurring" not in lower and "ask me before subscription" not in lower:
                recurring = True

        # Pincodes (Bangalore default demo: 560001, 560002, etc.)
        pincodes = re.findall(r'\b(560\d{3})\b', lower)
        if not pincodes:
            pincodes = ["560001", "560002", "560034", "560095"]

        return {
            "max_order_value_inr": single_order_cap,
            "max_aggregate_value_inr": agg_budget,
            "budget_period": period,
            "valid_days": valid_days,
            "categories_allowlist": categories,
            "merchants_allowlist": merchants,
            "recurring_allowed": recurring,
            "delivery_pincodes": list(set(pincodes))
        }

    @classmethod
    def _detect_ambiguities(
        cls,
        prompt: str,
        parsed: Dict[str, Any],
        confirmed: Optional[Dict[str, Any]]
    ) -> List[AmbiguityItem]:
        lower = prompt.lower()
        ambiguities = []

        # 1. Tax & Shipping Inclusion
        if "tax" not in lower and "shipping" not in lower and "all inclusive" not in lower:
            ambiguities.append(
                AmbiguityItem(
                    field="tax_and_fees",
                    question="Does your spending limit include taxes, delivery fees, and service charges?",
                    options=["Yes, all taxes and delivery fees must fit within the limit", "No, limit applies to subtotal only"],
                    default_assumption="Yes, all taxes and fees must be included in the authorized ceiling",
                    risk_level="MEDIUM"
                )
            )

        # 2. Substitution Permission
        if "substitut" not in lower and "alternative" not in lower:
            ambiguities.append(
                AmbiguityItem(
                    field="allow_substitutions",
                    question="If an exact product is unavailable, can the AI buyer substitute an equivalent brand?",
                    options=["Require my step-up approval for any substitution", "Allow automatic substitution within price limit"],
                    default_assumption="Require step-up approval for substitutions",
                    risk_level="HIGH"
                )
            )

        # 3. New / Unapproved Merchants
        if "merchant" not in lower and "store" not in lower:
            ambiguities.append(
                AmbiguityItem(
                    field="new_merchants",
                    question="Can the AI buyer purchase from newly discovered or unverified merchants?",
                    options=["Restricted to approved partner merchants only", "Allow any verified Razorpay merchant with step-up approval"],
                    default_assumption="Restricted to approved partner merchants only",
                    risk_level="HIGH"
                )
            )

        # 4. Recurring Subscription conversion
        if "subscription" not in lower and "recurring" not in lower:
            ambiguities.append(
                AmbiguityItem(
                    field="recurring_allowed",
                    question="Can the AI establish recurring weekly/monthly replenishment deliveries?",
                    options=["Strictly one-time purchases only", "Allow recurring orders under weekly cap"],
                    default_assumption="Strictly one-time purchases only",
                    risk_level="HIGH"
                )
            )

        return ambiguities
