"""Tamper-Evident SHA-256 Hash Chained Audit Log."""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from app.core.config import settings
from app.core.db import get_db, db_transaction
from app.audit.models import AuditEvent, ChainVerificationResult
from app.core.logging import logger


class AuditLogService:
    @staticmethod
    def _compute_hash(prev_hash: str, sequence_num: int, event_type: str, entity_id: str, payload_json: str, timestamp: str) -> str:
        # Canonical canonicalization of payload
        canonical_str = f"{prev_hash}|{sequence_num}|{event_type}|{entity_id}|{payload_json}|{timestamp}"
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    @classmethod
    def append_event(
        cls,
        event_type: str,
        entity_id: str,
        payload: Dict[str, Any],
        decision_id: Optional[str] = None
    ) -> AuditEvent:
        """Appends an event to the tamper-evident hash chain."""
        event_id = f"evt_{uuid.uuid4().hex[:10]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        payload_json = json.dumps(payload, sort_keys=True)

        with db_transaction() as cursor:
            # Get latest event in chain
            cursor.execute("SELECT sequence_num, current_hash FROM audit_events ORDER BY sequence_num DESC LIMIT 1")
            last_row = cursor.fetchone()

            if last_row:
                seq_num = int(last_row[0]) + 1
                prev_hash = str(last_row[1])
            else:
                seq_num = 1
                prev_hash = settings.AUDIT_GENESIS_HASH

            current_hash = cls._compute_hash(prev_hash, seq_num, event_type, entity_id, payload_json, now_iso)

            cursor.execute(
                """
                INSERT INTO audit_events (
                    event_id, sequence_num, event_type, entity_id, decision_id,
                    payload_json, prev_hash, current_hash, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (event_id, seq_num, event_type, entity_id, decision_id, payload_json, prev_hash, current_hash, now_iso)
            )

        logger.info(f"Audit event #{seq_num} ({event_type}) recorded with hash {current_hash[:12]}...")
        return AuditEvent(
            event_id=event_id,
            sequence_num=seq_num,
            event_type=event_type,
            entity_id=entity_id,
            decision_id=decision_id,
            payload_json=payload_json,
            prev_hash=prev_hash,
            current_hash=current_hash,
            timestamp=now_iso
        )

    @classmethod
    def verify_chain(cls) -> ChainVerificationResult:
        """Verifies the cryptographic integrity of the entire audit chain."""
        with get_db() as conn:
            rows = conn.execute("SELECT * FROM audit_events ORDER BY sequence_num ASC").fetchall()

        if not rows:
            return ChainVerificationResult(
                is_valid=True,
                total_events=0,
                genesis_hash=settings.AUDIT_GENESIS_HASH,
                latest_hash=settings.AUDIT_GENESIS_HASH
            )

        expected_prev_hash = settings.AUDIT_GENESIS_HASH
        for i, row in enumerate(rows):
            seq = int(row["sequence_num"])
            if seq != i + 1:
                return ChainVerificationResult(
                    is_valid=False,
                    total_events=len(rows),
                    genesis_hash=settings.AUDIT_GENESIS_HASH,
                    latest_hash=rows[-1]["current_hash"],
                    broken_at_sequence=seq,
                    error_message=f"Sequence number gap detected at index {i+1} (found sequence #{seq})."
                )

            if row["prev_hash"] != expected_prev_hash:
                return ChainVerificationResult(
                    is_valid=False,
                    total_events=len(rows),
                    genesis_hash=settings.AUDIT_GENESIS_HASH,
                    latest_hash=rows[-1]["current_hash"],
                    broken_at_sequence=seq,
                    error_message=f"Prev-hash mismatch at sequence #{seq}. Found '{row['prev_hash'][:12]}', expected '{expected_prev_hash[:12]}'."
                )

            recomputed_hash = cls._compute_hash(
                prev_hash=row["prev_hash"],
                sequence_num=seq,
                event_type=row["event_type"],
                entity_id=row["entity_id"],
                payload_json=row["payload_json"],
                timestamp=row["timestamp"]
            )

            if recomputed_hash != row["current_hash"]:
                return ChainVerificationResult(
                    is_valid=False,
                    total_events=len(rows),
                    genesis_hash=settings.AUDIT_GENESIS_HASH,
                    latest_hash=rows[-1]["current_hash"],
                    broken_at_sequence=seq,
                    error_message=f"Tampering detected: Payload or hash corrupted at sequence #{seq}."
                )

            expected_prev_hash = row["current_hash"]

        return ChainVerificationResult(
            is_valid=True,
            total_events=len(rows),
            genesis_hash=settings.AUDIT_GENESIS_HASH,
            latest_hash=rows[-1]["current_hash"]
        )

    @staticmethod
    def list_events(limit: int = 50) -> List[AuditEvent]:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_events ORDER BY sequence_num DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [
                AuditEvent(
                    event_id=r["event_id"],
                    sequence_num=r["sequence_num"],
                    event_type=r["event_type"],
                    entity_id=r["entity_id"],
                    decision_id=r["decision_id"],
                    payload_json=r["payload_json"],
                    prev_hash=r["prev_hash"],
                    current_hash=r["current_hash"],
                    timestamp=r["timestamp"]
                )
                for r in rows
            ]
