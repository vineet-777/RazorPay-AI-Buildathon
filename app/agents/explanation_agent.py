"""Grounded Decision Explanation Generator."""

from typing import Dict, Any
from app.authorization.models import AuthorizationDecision, DecisionEnum


class ExplanationAgent:
    """Generates human-readable explanations strictly grounded in deterministic rule outcomes."""

    @staticmethod
    def generate_explanation(decision: AuthorizationDecision) -> str:
        tx = decision.canonical_transaction
        amount = tx.get("total_inr", 0.0)
        merchant = tx.get("merchant_id", "unknown")
        sku = tx.get("sku", "unknown")

        if decision.decision == DecisionEnum.ALLOW:
            return (
                f"✅ Purchase of ₹{amount:,.2f} for '{sku}' from '{merchant}' was APPROVED. "
                f"All {len(decision.matched_rules)} policy rules were satisfied, and budget was reserved under contract "
                f"{decision.policy_versions.get('contract_id')}."
            )

        elif decision.decision == DecisionEnum.CHALLENGE:
            reasons = "; ".join(decision.challenge_reasons) if decision.challenge_reasons else decision.reason_code
            return (
                f"⚠️ Purchase of ₹{amount:,.2f} requires STEP-UP USER APPROVAL before money can be charged. "
                f"Trigger: {reasons}."
            )

        else:  # DENY
            failed = ", ".join(decision.failed_rules) if decision.failed_rules else decision.reason_code
            return (
                f"🛑 Purchase of ₹{amount:,.2f} for '{sku}' was BLOCKED by the deterministic authorization firewall. "
                f"Failed policy constraints: {failed}. Details: {decision.explanation}"
            )
