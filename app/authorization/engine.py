"""Central Deterministic Authorization Firewall."""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from app.core.db import get_db, db_transaction
from app.authorization.models import (
    CanonicalTransaction, AgentProposal, AuthorizationDecision,
    DecisionEnum, RuleImpactEnum, BudgetState
)
from app.authorization.contracts import ContractService, UserAuthorizationContract
from app.commerce.merchant_policy import MerchantPolicyService, MerchantPolicy
from app.commerce.catalog import CatalogService
from app.authorization.budget import BudgetEngine
from app.authorization.reservations import ReservationService
from app.authorization.rules import RuleEvaluator
from app.core.logging import logger


class AuthorizationFirewall:
    """The central deterministic trust layer that guards all money movement in Agent Commerce Gateway."""

    @classmethod
    def evaluate(
        cls,
        tx: CanonicalTransaction,
        proposal: Optional[AgentProposal] = None,
        override_merchant_policy_version: Optional[str] = None,
        is_simulation_replay: bool = False
    ) -> AuthorizationDecision:
        decision_id = f"dec_{uuid.uuid4().hex[:10]}"
        evaluated_at = datetime.now(timezone.utc).isoformat()
        logger.info(
            f"Evaluating transaction {tx.transaction_id} (Amount: ₹{tx.total_inr:,.2f}, Merchant: {tx.merchant_id}, SKU: {tx.sku}) [Simulation: {is_simulation_replay}]",
            extra={"transaction_id": tx.transaction_id, "decision_id": decision_id, "merchant_id": tx.merchant_id}
        )

        # 1. Fetch User Authorization Contract
        contract = ContractService.get_contract(tx.contract_id)
        if not contract:
            logger.warning(f"Contract '{tx.contract_id}' not found.")
            decision = AuthorizationDecision(
                decision_id=decision_id,
                transaction_id=tx.transaction_id,
                decision=DecisionEnum.DENY,
                matched_rules=[],
                failed_rules=["RULE_USER_CONTRACT_EXISTS"],
                challenge_reasons=[],
                policy_versions={"contract_version": 0, "merchant_policy_version": "none"},
                budget_state=BudgetState(
                    total_budget_inr=0, committed_spent_inr=0, active_reserved_inr=0,
                    available_budget_inr=0, requested_amount_inr=tx.total_inr, budget_period="unknown"
                ),
                reason_code="CONTRACT_NOT_FOUND",
                canonical_transaction=tx.model_dump(),
                agent_proposal=proposal.model_dump() if proposal else None,
                explanation=f"User authorization contract '{tx.contract_id}' does not exist.",
                evaluated_at=evaluated_at
            )
            if not is_simulation_replay:
                cls._persist_decision(decision)
            return decision

        # 2. Fetch Merchant AI Policy (Support version replay if specified)
        merchant_policy: Optional[MerchantPolicy] = None
        if override_merchant_policy_version:
            merchant_policy = MerchantPolicyService.get_policy_by_version(tx.merchant_id, override_merchant_policy_version)
        elif tx.merchant_policy_version:
            merchant_policy = MerchantPolicyService.get_policy_by_version(tx.merchant_id, tx.merchant_policy_version)
        else:
            merchant_policy = MerchantPolicyService.get_active_policy(tx.merchant_id)

        # 3. Fetch Product from Catalog (for inventory and AI eligibility checks)
        product = CatalogService.get_product(tx.sku)

        # 4. Compute Initial Budget State
        if is_simulation_replay:
            budget_state = BudgetState(
                total_budget_inr=contract.max_aggregate_value_inr,
                committed_spent_inr=0.0,
                active_reserved_inr=0.0,
                available_budget_inr=contract.max_aggregate_value_inr,
                requested_amount_inr=tx.total_inr,
                budget_period=contract.budget_period
            )
        else:
            budget_state = BudgetEngine.compute_budget_state(contract, requested_amount=tx.total_inr)

        # 5. Run Pure Rule Predicates
        outcomes = RuleEvaluator.evaluate_all(
            tx=tx,
            contract=contract,
            merchant_policy=merchant_policy,
            budget_state=budget_state,
            proposal=proposal,
            product=product
        )

        matched_rules = [o.rule_name for o in outcomes if o.passed]
        deny_outcomes = [o for o in outcomes if not o.passed and o.decision_impact == RuleImpactEnum.DENY]
        challenge_outcomes = [o for o in outcomes if not o.passed and o.decision_impact == RuleImpactEnum.CHALLENGE]

        policy_versions = {
            "contract_id": contract.contract_id,
            "contract_version": contract.version,
            "merchant_id": tx.merchant_id,
            "merchant_policy_version": merchant_policy.version if merchant_policy else "none"
        }

        # 6. Resolve Deterministic Decision
        final_decision: DecisionEnum
        reason_code: str
        explanation: str
        failed_rule_names = [o.rule_name for o in deny_outcomes]
        challenge_reasons = [o.reason for o in challenge_outcomes]

        if deny_outcomes:
            final_decision = DecisionEnum.DENY
            reason_code = deny_outcomes[0].rule_name
            explanation = f"Transaction blocked: {deny_outcomes[0].reason}"
        elif challenge_outcomes:
            final_decision = DecisionEnum.CHALLENGE
            reason_code = challenge_outcomes[0].rule_name
            explanation = f"Step-up approval required: {challenge_outcomes[0].reason}"
        else:
            if is_simulation_replay:
                # In simulation replay mode, evaluate if amount fits in aggregate ceiling without placing db reservation
                if tx.total_inr <= contract.max_aggregate_value_inr:
                    final_decision = DecisionEnum.ALLOW
                    reason_code = "ALL_CONSTRAINTS_SATISFIED"
                    explanation = f"Authorized (Simulation Replay): ₹{tx.total_inr:,.2f} satisfies policy {policy_versions['merchant_policy_version']}."
                else:
                    final_decision = DecisionEnum.DENY
                    reason_code = "RULE_USER_AGGREGATE_BUDGET"
                    failed_rule_names.append("RULE_USER_AGGREGATE_BUDGET")
                    explanation = f"Transaction blocked: Total ₹{tx.total_inr:,.2f} exceeds aggregate ceiling of ₹{contract.max_aggregate_value_inr:,.2f}."
            else:
                # All rules passed — execute atomic budget reservation
                reserved_ok, reservation_id, updated_budget = ReservationService.atomic_reserve(
                    contract=contract,
                    amount_inr=tx.total_inr,
                    transaction_id=tx.transaction_id,
                    decision_id=decision_id
                )
                if reserved_ok:
                    final_decision = DecisionEnum.ALLOW
                    reason_code = "ALL_CONSTRAINTS_SATISFIED"
                    explanation = f"Authorized: ₹{tx.total_inr:,.2f} reserved under contract {contract.contract_id}."
                    budget_state = updated_budget
                else:
                    final_decision = DecisionEnum.DENY
                    reason_code = "RULE_USER_AGGREGATE_BUDGET"
                    failed_rule_names.append("RULE_USER_AGGREGATE_BUDGET")
                    explanation = f"Transaction blocked: Insufficient remaining aggregate budget of ₹{updated_budget.available_budget_inr:,.2f}."
                    budget_state = updated_budget

        decision_obj = AuthorizationDecision(
            decision_id=decision_id,
            transaction_id=tx.transaction_id,
            decision=final_decision,
            matched_rules=matched_rules,
            failed_rules=failed_rule_names,
            challenge_reasons=challenge_reasons,
            policy_versions=policy_versions,
            budget_state=budget_state,
            reason_code=reason_code,
            canonical_transaction=tx.model_dump(),
            agent_proposal=proposal.model_dump() if proposal else None,
            explanation=explanation,
            evaluated_at=evaluated_at
        )

        if not is_simulation_replay:
            # Persist decision first
            cls._persist_decision(decision_obj)

            # If decision is CHALLENGE, record the step up challenge
            if final_decision == DecisionEnum.CHALLENGE:
                cls._create_step_up_challenge(decision_id, tx.transaction_id, challenge_reasons)

        return decision_obj

    @classmethod
    def _persist_decision(cls, decision: AuthorizationDecision) -> None:
        with db_transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO authorization_decisions (
                    decision_id, transaction_id, contract_id, contract_version,
                    merchant_id, merchant_policy_version, decision, matched_rules,
                    failed_rules, challenge_reasons, canonical_transaction,
                    agent_proposal, budget_state, reason_code, explanation, evaluated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(decision_id) DO UPDATE SET
                    decision=excluded.decision,
                    matched_rules=excluded.matched_rules,
                    failed_rules=excluded.failed_rules,
                    explanation=excluded.explanation
                """,
                (
                    decision.decision_id,
                    decision.transaction_id,
                    decision.policy_versions.get("contract_id", "none"),
                    decision.policy_versions.get("contract_version", 1),
                    decision.policy_versions.get("merchant_id", "none"),
                    decision.policy_versions.get("merchant_policy_version", "none"),
                    decision.decision.value,
                    json.dumps(decision.matched_rules),
                    json.dumps(decision.failed_rules),
                    json.dumps(decision.challenge_reasons),
                    json.dumps(decision.canonical_transaction),
                    json.dumps(decision.agent_proposal) if decision.agent_proposal else None,
                    json.dumps(decision.budget_state.model_dump()),
                    decision.reason_code,
                    decision.explanation,
                    decision.evaluated_at
                )
            )
        logger.info(f"Persisted decision {decision.decision_id} ({decision.decision.value}) for tx {decision.transaction_id}")

    @classmethod
    def _create_step_up_challenge(cls, decision_id: str, transaction_id: str, reasons: list) -> str:
        challenge_id = f"chal_{uuid.uuid4().hex[:10]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        with db_transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO step_up_challenges (
                    challenge_id, decision_id, transaction_id, status, reasons, created_at
                ) VALUES (?, ?, ?, 'PENDING', ?, ?)
                """,
                (challenge_id, decision_id, transaction_id, json.dumps(reasons), now_iso)
            )
        return challenge_id
