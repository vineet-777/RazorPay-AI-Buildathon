"""REST API Routes for Agent Commerce Gateway."""

import json
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Query, Header
from app.commerce.models import Product, MerchantPolicy, NegotiationRequest, NegotiationResponse
from app.commerce.catalog import CatalogService
from app.commerce.merchant_policy import MerchantPolicyService
from app.commerce.negotiation import NegotiationService
from app.authorization.models import (
    CanonicalTransaction, AgentProposal, AuthorizationDecision
)
from app.authorization.contracts import UserAuthorizationContract, ContractService
from app.authorization.engine import AuthorizationFirewall
from app.authorization.budget import BudgetEngine
from app.agents.policy_compiler import PolicyCompiler, PolicyCompilationRequest, PolicyCompilationResult
from app.agents.buyer_agent import BuyerAgent, ShoppingTaskRequest, ShoppingTaskResult
from app.payments.models import PaymentExecutionRequest, PaymentExecutionResponse
from app.payments.razorpay_client import RazorpayGatewayService
from app.audit.models import AuditEvent, ChainVerificationResult, ReplayComparisonResult
from app.audit.hash_chain import AuditLogService
from app.audit.replay import ReplayEngine
from app.core.db import get_db, db_transaction
from app.core.logging import logger

router = APIRouter(prefix="/api/v1")


# --- COMMERCE & CATALOG ENDPOINTS ---

@router.get("/commerce/catalog", response_model=List[Product], tags=["Commerce"])
def list_catalog(
    category: Optional[str] = Query(None, description="Filter by category"),
    merchant_id: Optional[str] = Query(None, description="Filter by merchant ID"),
    max_price: Optional[float] = Query(None, description="Maximum price limit"),
    query: Optional[str] = Query(None, description="Search query"),
    ai_enabled_only: bool = Query(True, description="Only return AI-commerce eligible products")
):
    """Discovers machine-readable products from merchant catalogs."""
    return CatalogService.list_products(
        category=category,
        merchant_id=merchant_id,
        max_price=max_price,
        query=query,
        ai_enabled_only=ai_enabled_only
    )


@router.get("/commerce/products/{sku}", response_model=Product, tags=["Commerce"])
def get_product(sku: str):
    """Retrieves structured product details by SKU."""
    product = CatalogService.get_product(sku)
    if not product:
        raise HTTPException(status_code=404, detail=f"Product with SKU '{sku}' not found.")
    return product


@router.post("/commerce/negotiate", response_model=NegotiationResponse, tags=["Commerce"])
def negotiate_terms(req: NegotiationRequest, merchant_id: str = Query(..., description="Target merchant ID")):
    """Negotiates purchase constraints (budget, delivery speed, installation) with a merchant."""
    return NegotiationService.evaluate_negotiation(req, merchant_id)


# --- MERCHANT POLICY ENDPOINTS ---

@router.get("/merchants/{merchant_id}/policies", response_model=List[MerchantPolicy], tags=["Merchant Policies"])
def list_merchant_policies(merchant_id: str):
    """Lists all historical and active policies for a merchant."""
    return MerchantPolicyService.list_policies_for_merchant(merchant_id)


@router.get("/merchants/{merchant_id}/policies/active", response_model=MerchantPolicy, tags=["Merchant Policies"])
def get_active_merchant_policy(merchant_id: str):
    """Retrieves the current active AI commerce policy for a merchant."""
    policy = MerchantPolicyService.get_active_policy(merchant_id)
    if not policy:
        raise HTTPException(status_code=404, detail=f"No active policy found for merchant '{merchant_id}'.")
    return policy


@router.post("/merchants/{merchant_id}/policies", response_model=MerchantPolicy, tags=["Merchant Policies"])
def create_merchant_policy_version(merchant_id: str, policy: MerchantPolicy):
    """Creates a new version of the merchant's AI commerce policy without mutating past history."""
    if policy.merchant_id != merchant_id:
        raise HTTPException(status_code=400, detail="Merchant ID mismatch in path and payload.")
    created = MerchantPolicyService.create_policy_version(policy)
    AuditLogService.append_event(
        event_type="POLICY_VERSION_CREATED",
        entity_id=merchant_id,
        payload={"merchant_id": merchant_id, "version": policy.version, "max_ai_order_value_inr": policy.max_ai_order_value_inr}
    )
    return created


# --- USER DELEGATION & AUTHORIZATION CONTRACTS ---

@router.post("/user/delegations/compile", response_model=PolicyCompilationResult, tags=["User Authorization"])
def compile_delegation(req: PolicyCompilationRequest):
    """Compiles natural-language delegation into a validated, machine-checkable policy contract."""
    return PolicyCompiler.compile(req)


@router.post("/user/delegations", response_model=UserAuthorizationContract, tags=["User Authorization"])
def create_authorization_contract(contract: UserAuthorizationContract):
    """Persists and activates a signed User Authorization Contract."""
    created = ContractService.create_contract(contract)
    AuditLogService.append_event(
        event_type="AUTHORIZATION_CONTRACT_CREATED",
        entity_id=contract.contract_id,
        payload={"contract_id": contract.contract_id, "principal_id": contract.principal_id, "max_order_inr": contract.max_order_value_inr}
    )
    return created


@router.get("/user/delegations/{contract_id}", response_model=Dict[str, Any], tags=["User Authorization"])
def get_contract_and_budget(contract_id: str):
    """Retrieves contract details and live real-time available budget."""
    contract = ContractService.get_contract(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail=f"Contract '{contract_id}' not found.")
    budget = BudgetEngine.compute_budget_state(contract)
    return {
        "contract": contract,
        "budget_state": budget
    }


@router.post("/user/delegations/{contract_id}/revoke", tags=["User Authorization"])
def revoke_authorization(contract_id: str):
    """Immediately revokes an active authorization contract."""
    ok = ContractService.revoke_contract(contract_id)
    AuditLogService.append_event(
        event_type="AUTHORIZATION_CONTRACT_REVOKED",
        entity_id=contract_id,
        payload={"contract_id": contract_id}
    )
    return {"success": ok, "message": f"Contract {contract_id} has been revoked."}


# --- AI BUYER AGENT WORKFLOW ---

@router.post("/agent/shop", response_model=ShoppingTaskResult, tags=["AI Buyer Agent"])
def run_buyer_agent(req: ShoppingTaskRequest):
    """Executes the complete autonomous shopping flow: discovery -> ranking -> proposal -> firewall -> payment."""
    result = BuyerAgent.execute_shopping_task(req)
    if result.authorization_decision:
        AuditLogService.append_event(
            event_type="SHOPPING_TASK_EXECUTED",
            entity_id=result.task_id,
            payload={
                "task_id": result.task_id,
                "goal": req.goal,
                "decision": result.status,
                "decision_id": result.authorization_decision.decision_id
            },
            decision_id=result.authorization_decision.decision_id
        )
    return result


# --- DETERMINISTIC GATEWAY & PAYMENTS ---

class AuthorizeRequest(BaseModel):
    canonical_transaction: CanonicalTransaction
    proposal: Optional[AgentProposal] = None


@router.post("/gateway/authorize", response_model=AuthorizationDecision, tags=["Authorization Firewall"])
def authorize_transaction(req: AuthorizeRequest):
    """Submits a canonical transaction to the deterministic authorization firewall."""
    decision = AuthorizationFirewall.evaluate(
        tx=req.canonical_transaction,
        proposal=req.proposal
    )
    AuditLogService.append_event(
        event_type="AUTHORIZATION_DECISION_EMITTED",
        entity_id=decision.decision_id,
        payload={
            "decision_id": decision.decision_id,
            "decision": decision.decision.value,
            "reason_code": decision.reason_code,
            "total_inr": req.canonical_transaction.total_inr
        },
        decision_id=decision.decision_id
    )
    return decision


@router.post("/gateway/pay", response_model=PaymentExecutionResponse, tags=["Payments"])
def execute_payment(req: PaymentExecutionRequest):
    """Executes a Razorpay test-mode payment for an ALLOWED decision."""
    resp = RazorpayGatewayService.execute_payment(req)
    AuditLogService.append_event(
        event_type="PAYMENT_EXECUTED" if resp.success else "PAYMENT_FAILED",
        entity_id=resp.payment_id,
        payload={
            "payment_id": resp.payment_id,
            "transaction_id": resp.transaction_id,
            "status": resp.status.value,
            "amount_inr": resp.amount_inr,
            "order_id": resp.razorpay_order_id
        },
        decision_id=req.decision_id
    )
    return resp


class StepUpResolveRequest(BaseModel):
    challenge_id: str
    approved: bool
    resolved_by: str = "principal_user"


@router.post("/gateway/challenges/resolve", tags=["Authorization Firewall"])
def resolve_step_up_challenge(req: StepUpResolveRequest):
    """Resolves a pending step-up challenge (ALLOW after manual approval or release reservation)."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM step_up_challenges WHERE challenge_id = ?", (req.challenge_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Challenge not found.")

    status = "APPROVED" if req.approved else "REJECTED"
    with db_transaction() as cursor:
        cursor.execute(
            "UPDATE step_up_challenges SET status = ?, resolved_by = ? WHERE challenge_id = ?",
            (status, req.resolved_by, req.challenge_id)
        )
    return {"challenge_id": req.challenge_id, "status": status, "resolved": True}


# --- AUDIT, DECISION TRACE & FORENSIC REPLAY ---

@router.get("/audit/events", response_model=List[AuditEvent], tags=["Audit & Forensic"])
def list_audit_events(limit: int = Query(50, ge=1, le=200)):
    """Fetches recent events from the append-only tamper-evident audit log."""
    return AuditLogService.list_events(limit=limit)


@router.get("/audit/verify-chain", response_model=ChainVerificationResult, tags=["Audit & Forensic"])
def verify_audit_chain():
    """Cryptographically verifies the SHA-256 hash chain of the entire audit trail."""
    return AuditLogService.verify_chain()


@router.get("/audit/decisions/{decision_id}", response_model=Dict[str, Any], tags=["Audit & Forensic"])
def inspect_decision_trace(decision_id: str):
    """Retrieves full causal evidence trace for a specific decision ID."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM authorization_decisions WHERE decision_id = ?", (decision_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Decision '{decision_id}' not found.")

    return {
        "decision_id": row["decision_id"],
        "transaction_id": row["transaction_id"],
        "contract_id": row["contract_id"],
        "contract_version": row["contract_version"],
        "merchant_id": row["merchant_id"],
        "merchant_policy_version": row["merchant_policy_version"],
        "decision": row["decision"],
        "matched_rules": json.loads(row["matched_rules"]),
        "failed_rules": json.loads(row["failed_rules"]),
        "challenge_reasons": json.loads(row["challenge_reasons"]),
        "canonical_transaction": json.loads(row["canonical_transaction"]),
        "agent_proposal": json.loads(row["agent_proposal"]) if row["agent_proposal"] else None,
        "budget_state": json.loads(row["budget_state"]),
        "reason_code": row["reason_code"],
        "explanation": row["explanation"],
        "evaluated_at": row["evaluated_at"]
    }


class ReplayRequest(BaseModel):
    decision_id: str
    target_merchant_policy_version: Optional[str] = None


@router.post("/audit/replay", response_model=ReplayComparisonResult, tags=["Audit & Forensic"])
def replay_decision(req: ReplayRequest):
    """Replays a historical transaction deterministically against historical or new policy versions."""
    try:
        return ReplayEngine.replay_decision(
            decision_id=req.decision_id,
            target_merchant_policy_version=req.target_merchant_policy_version
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
