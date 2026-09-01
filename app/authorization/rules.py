"""Pure deterministic rule predicates for Authorization Firewall."""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple
from app.authorization.models import CanonicalTransaction, AgentProposal, BudgetState, RuleOutcome, RuleImpactEnum
from app.authorization.contracts import UserAuthorizationContract
from app.commerce.models import MerchantPolicy, Product


class RuleEvaluator:
    """Evaluates pure deterministic authorization predicates against transaction facts and policies."""

    @staticmethod
    def evaluate_all(
        tx: CanonicalTransaction,
        contract: UserAuthorizationContract,
        merchant_policy: Optional[MerchantPolicy],
        budget_state: BudgetState,
        proposal: Optional[AgentProposal] = None,
        product: Optional[Product] = None
    ) -> List[RuleOutcome]:
        outcomes: List[RuleOutcome] = []

        # 1. User Contract Expiry & Revocation
        outcomes.append(RuleEvaluator.check_contract_expiry(tx, contract))
        outcomes.append(RuleEvaluator.check_contract_revocation(tx, contract))

        # 2. User Policy Constraints
        outcomes.append(RuleEvaluator.check_user_merchant_allowlist(tx, contract))
        outcomes.append(RuleEvaluator.check_user_category_allowlist(tx, contract))
        outcomes.append(RuleEvaluator.check_user_single_order_cap(tx, contract))
        outcomes.append(RuleEvaluator.check_user_aggregate_budget(tx, contract, budget_state))
        outcomes.append(RuleEvaluator.check_user_recurring_permission(tx, contract))
        outcomes.append(RuleEvaluator.check_user_pincode(tx, contract))

        # 3. Currency & Basic Fact Integrity
        outcomes.append(RuleEvaluator.check_currency(tx))
        outcomes.append(RuleEvaluator.check_fee_integrity(tx))

        # 4. Merchant Policy Constraints
        if merchant_policy:
            outcomes.append(RuleEvaluator.check_merchant_ai_enabled(tx, merchant_policy))
            outcomes.append(RuleEvaluator.check_merchant_order_cap(tx, merchant_policy))
            outcomes.append(RuleEvaluator.check_merchant_category(tx, merchant_policy))
            outcomes.append(RuleEvaluator.check_merchant_substitutions(tx, merchant_policy, proposal))
        else:
            outcomes.append(
                RuleOutcome(
                    rule_name="RULE_MERCHANT_POLICY_PRESENT",
                    passed=False,
                    decision_impact=RuleImpactEnum.DENY,
                    reason=f"No active merchant policy found for merchant '{tx.merchant_id}'."
                )
            )

        # 5. Product Inventory & AI Catalog Eligibility
        if product:
            outcomes.append(RuleEvaluator.check_product_inventory(tx, product))
            outcomes.append(RuleEvaluator.check_product_ai_enabled(tx, product))

        # 6. Transaction Mutation & Integrity Checks (against Agent Proposal)
        if proposal:
            outcomes.append(RuleEvaluator.check_mutation_merchant(tx, proposal))
            outcomes.append(RuleEvaluator.check_mutation_sku(tx, proposal, contract))
            outcomes.append(RuleEvaluator.check_mutation_price_drift(tx, proposal, contract))
            outcomes.append(RuleEvaluator.check_mutation_quantity(tx, proposal))
            outcomes.append(RuleEvaluator.check_mutation_recurring(tx, proposal))

        return outcomes

    # --- INDIVIDUAL RULE PREDICATES ---

    @staticmethod
    def check_contract_expiry(tx: CanonicalTransaction, contract: UserAuthorizationContract) -> RuleOutcome:
        now = datetime.now(timezone.utc)
        try:
            expires_at = datetime.fromisoformat(contract.expires_at.replace("Z", "+00:00"))
            if now > expires_at:
                return RuleOutcome(
                    rule_name="RULE_USER_CONTRACT_EXPIRY",
                    passed=False,
                    decision_impact=RuleImpactEnum.DENY,
                    reason=f"User authorization contract expired at {contract.expires_at} (Current time: {now.isoformat()})."
                )
        except Exception as e:
            return RuleOutcome(
                rule_name="RULE_USER_CONTRACT_EXPIRY",
                passed=False,
                decision_impact=RuleImpactEnum.DENY,
                reason=f"Invalid contract expiration date format: {contract.expires_at}."
            )
        return RuleOutcome(
            rule_name="RULE_USER_CONTRACT_EXPIRY",
            passed=True,
            decision_impact=RuleImpactEnum.ALLOW,
            reason="User authorization contract is actively valid."
        )

    @staticmethod
    def check_contract_revocation(tx: CanonicalTransaction, contract: UserAuthorizationContract) -> RuleOutcome:
        if contract.is_revoked:
            return RuleOutcome(
                rule_name="RULE_USER_CONTRACT_REVOCATION",
                passed=False,
                decision_impact=RuleImpactEnum.DENY,
                reason=f"User authorization contract {contract.contract_id} was revoked by the principal."
            )
        return RuleOutcome(
            rule_name="RULE_USER_CONTRACT_REVOCATION",
            passed=True,
            decision_impact=RuleImpactEnum.ALLOW,
            reason="User authorization contract has not been revoked."
        )

    @staticmethod
    def check_user_merchant_allowlist(tx: CanonicalTransaction, contract: UserAuthorizationContract) -> RuleOutcome:
        if contract.merchants_allowlist and tx.merchant_id not in contract.merchants_allowlist:
            # Check if step up is allowed for new merchants or strictly blocked
            if "new_merchant" in contract.approval_conditions:
                return RuleOutcome(
                    rule_name="RULE_USER_MERCHANT_ALLOWLIST",
                    passed=False,
                    decision_impact=RuleImpactEnum.CHALLENGE,
                    reason=f"Merchant '{tx.merchant_id}' is not in approved merchant allowlist. Step-up approval required."
                )
            return RuleOutcome(
                rule_name="RULE_USER_MERCHANT_ALLOWLIST",
                passed=False,
                decision_impact=RuleImpactEnum.DENY,
                reason=f"Merchant '{tx.merchant_id}' is not permitted by user authorization."
            )
        return RuleOutcome(
            rule_name="RULE_USER_MERCHANT_ALLOWLIST",
            passed=True,
            decision_impact=RuleImpactEnum.ALLOW,
            reason=f"Merchant '{tx.merchant_id}' is in user approved allowlist."
        )

    @staticmethod
    def check_user_category_allowlist(tx: CanonicalTransaction, contract: UserAuthorizationContract) -> RuleOutcome:
        if contract.categories_allowlist and tx.category not in contract.categories_allowlist:
            return RuleOutcome(
                rule_name="RULE_USER_CATEGORY_ALLOWLIST",
                passed=False,
                decision_impact=RuleImpactEnum.DENY,
                reason=f"Category '{tx.category}' is not permitted under delegated contract allowlist {contract.categories_allowlist}."
            )
        return RuleOutcome(
            rule_name="RULE_USER_CATEGORY_ALLOWLIST",
            passed=True,
            decision_impact=RuleImpactEnum.ALLOW,
            reason=f"Category '{tx.category}' is permitted."
        )

    @staticmethod
    def check_user_single_order_cap(tx: CanonicalTransaction, contract: UserAuthorizationContract) -> RuleOutcome:
        if tx.total_inr > contract.max_order_value_inr:
            return RuleOutcome(
                rule_name="RULE_USER_SINGLE_ORDER_CAP",
                passed=False,
                decision_impact=RuleImpactEnum.DENY,
                reason=f"Transaction total ₹{tx.total_inr:,.2f} exceeds user single-order limit of ₹{contract.max_order_value_inr:,.2f}."
            )
        return RuleOutcome(
            rule_name="RULE_USER_SINGLE_ORDER_CAP",
            passed=True,
            decision_impact=RuleImpactEnum.ALLOW,
            reason=f"Transaction total ₹{tx.total_inr:,.2f} is within single-order cap of ₹{contract.max_order_value_inr:,.2f}."
        )

    @staticmethod
    def check_user_aggregate_budget(
        tx: CanonicalTransaction,
        contract: UserAuthorizationContract,
        budget_state: BudgetState
    ) -> RuleOutcome:
        if tx.total_inr > budget_state.available_budget_inr:
            return RuleOutcome(
                rule_name="RULE_USER_AGGREGATE_BUDGET",
                passed=False,
                decision_impact=RuleImpactEnum.DENY,
                reason=f"Transaction ₹{tx.total_inr:,.2f} exceeds remaining available {budget_state.budget_period} budget of ₹{budget_state.available_budget_inr:,.2f} (Total: ₹{budget_state.total_budget_inr:,.2f}, Spent: ₹{budget_state.committed_spent_inr:,.2f}, Reserved: ₹{budget_state.active_reserved_inr:,.2f})."
            )
        return RuleOutcome(
            rule_name="RULE_USER_AGGREGATE_BUDGET",
            passed=True,
            decision_impact=RuleImpactEnum.ALLOW,
            reason=f"Transaction ₹{tx.total_inr:,.2f} fits within remaining available budget of ₹{budget_state.available_budget_inr:,.2f}."
        )

    @staticmethod
    def check_user_recurring_permission(tx: CanonicalTransaction, contract: UserAuthorizationContract) -> RuleOutcome:
        if tx.recurring and not contract.recurring_allowed:
            return RuleOutcome(
                rule_name="RULE_USER_RECURRING_PERMISSION",
                passed=False,
                decision_impact=RuleImpactEnum.DENY,
                reason="Transaction requested recurring subscription payment, but recurring purchases are explicitly disabled in user contract."
            )
        return RuleOutcome(
            rule_name="RULE_USER_RECURRING_PERMISSION",
            passed=True,
            decision_impact=RuleImpactEnum.ALLOW,
            reason="Recurring payment constraint satisfied."
        )

    @staticmethod
    def check_user_pincode(tx: CanonicalTransaction, contract: UserAuthorizationContract) -> RuleOutcome:
        if contract.delivery_pincodes and tx.destination_pincode:
            if tx.destination_pincode not in contract.delivery_pincodes:
                if "unapproved_pincode" in contract.approval_conditions:
                    return RuleOutcome(
                        rule_name="RULE_USER_PINCODE_RESTRICTION",
                        passed=False,
                        decision_impact=RuleImpactEnum.CHALLENGE,
                        reason=f"Destination pincode '{tx.destination_pincode}' is not in approved pincodes list {contract.delivery_pincodes}. Step-up approval required."
                    )
                return RuleOutcome(
                    rule_name="RULE_USER_PINCODE_RESTRICTION",
                    passed=False,
                    decision_impact=RuleImpactEnum.DENY,
                    reason=f"Destination pincode '{tx.destination_pincode}' is not allowed."
                )
        return RuleOutcome(
            rule_name="RULE_USER_PINCODE_RESTRICTION",
            passed=True,
            decision_impact=RuleImpactEnum.ALLOW,
            reason="Destination pincode verified."
        )

    @staticmethod
    def check_currency(tx: CanonicalTransaction) -> RuleOutcome:
        if tx.currency.upper() != "INR":
            return RuleOutcome(
                rule_name="RULE_CURRENCY_MATCH",
                passed=False,
                decision_impact=RuleImpactEnum.DENY,
                reason=f"Unsupported currency '{tx.currency}'. Razorpay test-mode gateway only accepts INR."
            )
        return RuleOutcome(
            rule_name="RULE_CURRENCY_MATCH",
            passed=True,
            decision_impact=RuleImpactEnum.ALLOW,
            reason="Currency is valid INR."
        )

    @staticmethod
    def check_fee_integrity(tx: CanonicalTransaction) -> RuleOutcome:
        calculated_total = round(tx.subtotal_inr - tx.discount_inr + tx.tax_inr + tx.shipping_inr, 2)
        if abs(calculated_total - tx.total_inr) > 0.05:
            return RuleOutcome(
                rule_name="RULE_TRANSACTION_FEE_INTEGRITY",
                passed=False,
                decision_impact=RuleImpactEnum.DENY,
                reason=f"Transaction total mismatch (Declared: ₹{tx.total_inr:,.2f}, Calculated subtotal+tax+shipping-discount: ₹{calculated_total:,.2f})."
            )
        return RuleOutcome(
            rule_name="RULE_TRANSACTION_FEE_INTEGRITY",
            passed=True,
            decision_impact=RuleImpactEnum.ALLOW,
            reason="Transaction arithmetic fee integrity verified."
        )

    # --- MERCHANT POLICY RULES ---

    @staticmethod
    def check_merchant_ai_enabled(tx: CanonicalTransaction, policy: MerchantPolicy) -> RuleOutcome:
        if not policy.ai_sales_enabled:
            return RuleOutcome(
                rule_name="RULE_MERCHANT_AI_COMMERCE_ENABLED",
                passed=False,
                decision_impact=RuleImpactEnum.DENY,
                reason=f"Merchant '{tx.merchant_id}' has disabled autonomous AI commerce transactions."
            )
        return RuleOutcome(
            rule_name="RULE_MERCHANT_AI_COMMERCE_ENABLED",
            passed=True,
            decision_impact=RuleImpactEnum.ALLOW,
            reason="Merchant allows autonomous AI transactions."
        )

    @staticmethod
    def check_merchant_order_cap(tx: CanonicalTransaction, policy: MerchantPolicy) -> RuleOutcome:
        if tx.total_inr > policy.max_ai_order_value_inr:
            # Check if merchant policy permits high value order with step-up challenge
            if "high_value_order" in policy.require_step_up_rules:
                return RuleOutcome(
                    rule_name="RULE_MERCHANT_MAX_ORDER_CAP",
                    passed=False,
                    decision_impact=RuleImpactEnum.CHALLENGE,
                    reason=f"Transaction amount ₹{tx.total_inr:,.2f} exceeds merchant autonomous threshold of ₹{policy.max_ai_order_value_inr:,.2f} under policy {policy.version}. Step-up approval required."
                )
            return RuleOutcome(
                rule_name="RULE_MERCHANT_MAX_ORDER_CAP",
                passed=False,
                decision_impact=RuleImpactEnum.DENY,
                reason=f"Transaction amount ₹{tx.total_inr:,.2f} exceeds merchant hard cap of ₹{policy.max_ai_order_value_inr:,.2f} under policy {policy.version}."
            )
        return RuleOutcome(
            rule_name="RULE_MERCHANT_MAX_ORDER_CAP",
            passed=True,
            decision_impact=RuleImpactEnum.ALLOW,
            reason=f"Transaction amount ₹{tx.total_inr:,.2f} is within merchant policy {policy.version} limit of ₹{policy.max_ai_order_value_inr:,.2f}."
        )

    @staticmethod
    def check_merchant_category(tx: CanonicalTransaction, policy: MerchantPolicy) -> RuleOutcome:
        if policy.allowed_categories and tx.category not in policy.allowed_categories:
            return RuleOutcome(
                rule_name="RULE_MERCHANT_CATEGORY_RESTRICTION",
                passed=False,
                decision_impact=RuleImpactEnum.DENY,
                reason=f"Category '{tx.category}' is not allowed by merchant policy {policy.version} (Allowed: {policy.allowed_categories})."
            )
        return RuleOutcome(
            rule_name="RULE_MERCHANT_CATEGORY_RESTRICTION",
            passed=True,
            decision_impact=RuleImpactEnum.ALLOW,
            reason="Category permitted by merchant policy."
        )

    @staticmethod
    def check_merchant_substitutions(
        tx: CanonicalTransaction,
        policy: MerchantPolicy,
        proposal: Optional[AgentProposal]
    ) -> RuleOutcome:
        if proposal and proposal.sku != tx.sku and not policy.allow_substitutions:
            if "product_substitution" in policy.require_step_up_rules:
                return RuleOutcome(
                    rule_name="RULE_MERCHANT_SUBSTITUTION_POLICY",
                    passed=False,
                    decision_impact=RuleImpactEnum.CHALLENGE,
                    reason=f"Product SKU substitution from '{proposal.sku}' to '{tx.sku}' requires merchant step-up approval."
                )
            return RuleOutcome(
                rule_name="RULE_MERCHANT_SUBSTITUTION_POLICY",
                passed=False,
                decision_impact=RuleImpactEnum.DENY,
                reason=f"Merchant policy {policy.version} strictly disallows product substitutions."
            )
        return RuleOutcome(
            rule_name="RULE_MERCHANT_SUBSTITUTION_POLICY",
            passed=True,
            decision_impact=RuleImpactEnum.ALLOW,
            reason="Substitution policy satisfied."
        )

    # --- PRODUCT INVENTORY & AI ELIGIBILITY ---

    @staticmethod
    def check_product_inventory(tx: CanonicalTransaction, product: Product) -> RuleOutcome:
        if product.inventory < tx.quantity:
            return RuleOutcome(
                rule_name="RULE_PRODUCT_INVENTORY_AVAILABLE",
                passed=False,
                decision_impact=RuleImpactEnum.DENY,
                reason=f"Requested quantity {tx.quantity} exceeds available inventory of {product.inventory}."
            )
        return RuleOutcome(
            rule_name="RULE_PRODUCT_INVENTORY_AVAILABLE",
            passed=True,
            decision_impact=RuleImpactEnum.ALLOW,
            reason=f"Inventory available ({product.inventory} in stock)."
        )

    @staticmethod
    def check_product_ai_enabled(tx: CanonicalTransaction, product: Product) -> RuleOutcome:
        if not product.ai_enabled:
            return RuleOutcome(
                rule_name="RULE_PRODUCT_AI_ELIGIBILITY",
                passed=False,
                decision_impact=RuleImpactEnum.DENY,
                reason=f"Product SKU '{product.sku}' is not eligible for autonomous AI checkout."
            )
        return RuleOutcome(
            rule_name="RULE_PRODUCT_AI_ELIGIBILITY",
            passed=True,
            decision_impact=RuleImpactEnum.ALLOW,
            reason="Product SKU is AI checkout eligible."
        )

    # --- TRANSACTION MUTATION DEFENSES ---

    @staticmethod
    def check_mutation_merchant(tx: CanonicalTransaction, proposal: AgentProposal) -> RuleOutcome:
        if tx.merchant_id != proposal.merchant_id:
            return RuleOutcome(
                rule_name="RULE_TRANSACTION_MUTATION_MERCHANT",
                passed=False,
                decision_impact=RuleImpactEnum.DENY,
                reason=f"Material mutation detected: Executable merchant '{tx.merchant_id}' does not match original proposed merchant '{proposal.merchant_id}'."
            )
        return RuleOutcome(
            rule_name="RULE_TRANSACTION_MUTATION_MERCHANT",
            passed=True,
            decision_impact=RuleImpactEnum.ALLOW,
            reason="Merchant identity verified against proposal."
        )

    @staticmethod
    def check_mutation_sku(
        tx: CanonicalTransaction,
        proposal: AgentProposal,
        contract: UserAuthorizationContract
    ) -> RuleOutcome:
        if tx.sku != proposal.sku:
            if "substituted_sku" in contract.approval_conditions:
                return RuleOutcome(
                    rule_name="RULE_TRANSACTION_MUTATION_SKU",
                    passed=False,
                    decision_impact=RuleImpactEnum.CHALLENGE,
                    reason=f"Material mutation detected: Executable SKU '{tx.sku}' differs from proposed SKU '{proposal.sku}'. Step-up approval required."
                )
            return RuleOutcome(
                rule_name="RULE_TRANSACTION_MUTATION_SKU",
                passed=False,
                decision_impact=RuleImpactEnum.DENY,
                reason=f"Material mutation detected: Executable SKU '{tx.sku}' does not match proposed SKU '{proposal.sku}'."
            )
        return RuleOutcome(
            rule_name="RULE_TRANSACTION_MUTATION_SKU",
            passed=True,
            decision_impact=RuleImpactEnum.ALLOW,
            reason="SKU identity verified against proposal."
        )

    @staticmethod
    def check_mutation_price_drift(
        tx: CanonicalTransaction,
        proposal: AgentProposal,
        contract: UserAuthorizationContract
    ) -> RuleOutcome:
        drift_ratio = (tx.total_inr - proposal.estimated_total_inr) / max(proposal.estimated_total_inr, 1.0)
        if drift_ratio > 0.10:  # > 10% price increase
            if "price_increase_over_10_percent" in contract.approval_conditions:
                return RuleOutcome(
                    rule_name="RULE_TRANSACTION_MUTATION_PRICE_DRIFT",
                    passed=False,
                    decision_impact=RuleImpactEnum.CHALLENGE,
                    reason=f"Material mutation detected: Final total ₹{tx.total_inr:,.2f} is {drift_ratio*100:.1f}% higher than estimated ₹{proposal.estimated_total_inr:,.2f}. Step-up approval required."
                )
            return RuleOutcome(
                rule_name="RULE_TRANSACTION_MUTATION_PRICE_DRIFT",
                passed=False,
                decision_impact=RuleImpactEnum.DENY,
                reason=f"Material mutation detected: Final total ₹{tx.total_inr:,.2f} exceeds proposed ₹{proposal.estimated_total_inr:,.2f} by {drift_ratio*100:.1f}%."
            )
        return RuleOutcome(
            rule_name="RULE_TRANSACTION_MUTATION_PRICE_DRIFT",
            passed=True,
            decision_impact=RuleImpactEnum.ALLOW,
            reason="Price drift within acceptable bounds."
        )

    @staticmethod
    def check_mutation_quantity(tx: CanonicalTransaction, proposal: AgentProposal) -> RuleOutcome:
        if tx.quantity != proposal.quantity:
            return RuleOutcome(
                rule_name="RULE_TRANSACTION_MUTATION_QUANTITY",
                passed=False,
                decision_impact=RuleImpactEnum.DENY,
                reason=f"Material mutation detected: Quantity changed from {proposal.quantity} to {tx.quantity}."
            )
        return RuleOutcome(
            rule_name="RULE_TRANSACTION_MUTATION_QUANTITY",
            passed=True,
            decision_impact=RuleImpactEnum.ALLOW,
            reason="Quantity verified against proposal."
        )

    @staticmethod
    def check_mutation_recurring(tx: CanonicalTransaction, proposal: AgentProposal) -> RuleOutcome:
        if tx.recurring and not proposal.recurring:
            return RuleOutcome(
                rule_name="RULE_TRANSACTION_MUTATION_RECURRING",
                passed=False,
                decision_impact=RuleImpactEnum.DENY,
                reason="Material mutation detected: One-time proposed purchase was converted into a recurring subscription at execution time."
            )
        return RuleOutcome(
            rule_name="RULE_TRANSACTION_MUTATION_RECURRING",
            passed=True,
            decision_impact=RuleImpactEnum.ALLOW,
            reason="Recurring flag matches proposal."
        )
