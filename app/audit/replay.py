"""Deterministic Forensic Replay Engine."""

import json
from typing import Optional, Dict, Any
from app.core.db import get_db
from app.authorization.models import (
    CanonicalTransaction, AgentProposal, AuthorizationDecision
)
from app.authorization.engine import AuthorizationFirewall
from app.audit.models import ReplayComparisonResult
from app.core.logging import logger


class ReplayEngine:
    @staticmethod
    def replay_decision(
        decision_id: str,
        target_merchant_policy_version: Optional[str] = None
    ) -> ReplayComparisonResult:
        """Replays a historical transaction deterministically against historical or new policy versions."""
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM authorization_decisions WHERE decision_id = ?",
                (decision_id,)
            ).fetchone()

        if not row:
            raise ValueError(f"Decision '{decision_id}' not found in audit logs.")

        canonical_dict = json.loads(row["canonical_transaction"])
        proposal_dict = json.loads(row["agent_proposal"]) if row["agent_proposal"] else None

        canonical_tx = CanonicalTransaction(**canonical_dict)
        proposal = AgentProposal(**proposal_dict) if proposal_dict else None

        hist_decision = row["decision"]
        hist_matched = json.loads(row["matched_rules"])
        hist_failed = json.loads(row["failed_rules"])
        hist_policy_ver = row["merchant_policy_version"]

        # Run re-evaluation through deterministic firewall in simulation replay mode
        replayed_decision_obj = AuthorizationFirewall.evaluate(
            tx=canonical_tx,
            proposal=proposal,
            override_merchant_policy_version=target_merchant_policy_version,
            is_simulation_replay=True
        )

        replayed_decision = replayed_decision_obj.decision.value
        replayed_policy_ver = replayed_decision_obj.policy_versions.get("merchant_policy_version", "unknown")
        is_identical = (hist_decision == replayed_decision and hist_matched == replayed_decision_obj.matched_rules)

        if is_identical:
            summary = f"Replay verified 100% deterministic reproducibility under policy {replayed_policy_ver} (Decision: {replayed_decision})."
        else:
            summary = (
                f"Policy version change ({hist_policy_ver} -> {replayed_policy_ver}) altered decision from "
                f"'{hist_decision}' to '{replayed_decision}'."
            )

        logger.info(f"Replay completed for decision {decision_id}: {summary}")

        return ReplayComparisonResult(
            decision_id=decision_id,
            transaction_id=canonical_tx.transaction_id,
            historical_policy_version=hist_policy_ver,
            historical_decision=hist_decision,
            historical_matched_rules=hist_matched,
            historical_failed_rules=hist_failed,
            replayed_policy_version=replayed_policy_ver,
            replayed_decision=replayed_decision,
            replayed_matched_rules=replayed_decision_obj.matched_rules,
            replayed_failed_rules=replayed_decision_obj.failed_rules,
            is_decision_identical=is_identical,
            policy_impact_summary=summary,
            replayed_decision_object=replayed_decision_obj
        )
