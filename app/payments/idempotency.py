"""Idempotency Layer for Payment and Transaction Execution."""

import json
from typing import Optional, Tuple
from app.core.db import get_db, db_transaction
from app.core.logging import logger


class IdempotencyService:
    @staticmethod
    def check_idempotency(idempotency_key: str) -> Optional[dict]:
        """Checks if a transaction with this idempotency key already exists."""
        if not idempotency_key:
            return None

        with get_db() as conn:
            row = conn.execute(
                """
                SELECT t.transaction_id, t.status, t.total_inr, t.merchant_id, t.sku,
                       p.payment_id, p.razorpay_order_id, p.razorpay_payment_id, p.signature
                FROM transactions t
                LEFT JOIN payment_attempts p ON t.transaction_id = p.transaction_id
                WHERE t.idempotency_key = ?
                ORDER BY p.created_at DESC LIMIT 1
                """,
                (idempotency_key,)
            ).fetchone()

            if row:
                logger.info(f"Idempotency hit for key '{idempotency_key}'. Returning existing transaction {row['transaction_id']}")
                return dict(row)
            return None
