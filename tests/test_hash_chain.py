"""Unit tests for SHA-256 Tamper-Evident Hash Chained Audit Trail."""

import pytest
from app.core.db import db_transaction
from app.audit.hash_chain import AuditLogService


def test_hash_chain_append_and_verify():
    evt1 = AuditLogService.append_event(
        event_type="TEST_EVENT_1",
        entity_id="test_01",
        payload={"action": "create_contract", "amount": 5000}
    )
    assert evt1.sequence_num > 0
    assert len(evt1.current_hash) == 64

    evt2 = AuditLogService.append_event(
        event_type="TEST_EVENT_2",
        entity_id="test_02",
        payload={"action": "evaluate_transaction", "decision": "ALLOW"}
    )
    assert evt2.sequence_num == evt1.sequence_num + 1
    assert evt2.prev_hash == evt1.current_hash

    # Verify chain integrity
    res = AuditLogService.verify_chain()
    assert res.is_valid is True
    assert res.total_events >= 2


def test_hash_chain_tampering_detection():
    AuditLogService.append_event(
        event_type="UNMUTATED_EVENT",
        entity_id="entity_99",
        payload={"secret": "original_payload"}
    )

    # Intentionally corrupt payload in database
    with db_transaction() as cursor:
        cursor.execute("UPDATE audit_events SET payload_json = '{\"secret\": \"tampered_data\"}' WHERE sequence_num = 1")

    # Verifier should catch corruption
    res = AuditLogService.verify_chain()
    assert res.is_valid is False
    assert res.broken_at_sequence == 1
    assert "Tampering detected" in res.error_message
