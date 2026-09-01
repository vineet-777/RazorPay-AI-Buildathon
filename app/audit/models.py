"""Data models for Audit Trail and Forensic Replay."""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from app.authorization.models import AuthorizationDecision


class AuditEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    sequence_num: int
    event_type: str  # e.g. "AUTHORIZATION_EVALUATED", "BUDGET_RESERVED", "PAYMENT_EXECUTED", "POLICY_UPDATED"
    entity_id: str
    decision_id: Optional[str] = None
    payload_json: str
    prev_hash: str
    current_hash: str
    timestamp: str


class ChainVerificationResult(BaseModel):
    is_valid: bool
    total_events: int
    genesis_hash: str
    latest_hash: str
    broken_at_sequence: Optional[int] = None
    error_message: Optional[str] = None


class ReplayComparisonResult(BaseModel):
    decision_id: str
    transaction_id: str
    historical_policy_version: str
    historical_decision: str
    historical_matched_rules: List[str]
    historical_failed_rules: List[str]

    replayed_policy_version: str
    replayed_decision: str
    replayed_matched_rules: List[str]
    replayed_failed_rules: List[str]

    is_decision_identical: bool
    policy_impact_summary: str
    replayed_decision_object: AuthorizationDecision
