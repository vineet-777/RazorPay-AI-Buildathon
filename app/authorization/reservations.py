"""Concurrency-safe Atomic Budget Reservation Manager."""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Tuple, Optional
from app.core.db import db_transaction, get_db
from app.authorization.models import BudgetState
from app.authorization.contracts import UserAuthorizationContract
from app.authorization.budget import BudgetEngine
from app.core.logging import logger


class ReservationService:
    @staticmethod
    def atomic_reserve(
        contract: UserAuthorizationContract,
        amount_inr: float,
        transaction_id: str,
        decision_id: str,
        timeout_minutes: int = 15
    ) -> Tuple[bool, Optional[str], BudgetState]:
        """Atomically checks remaining budget and places a reservation using SQLite immediate lock."""
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        expires_iso = (now + timedelta(minutes=timeout_minutes)).isoformat()
        window_start = BudgetEngine.get_budget_window_start(contract)
        reservation_id = f"res_{uuid.uuid4().hex[:10]}"

        is_per_order = (contract.budget_period.lower() == "per_order")

        with db_transaction() as cursor:
            # 1. Re-calculate committed spent inside lock (0 if per_order)
            committed_spent = 0.0
            if not is_per_order:
                cursor.execute(
                    """
                    SELECT COALESCE(SUM(amount_inr), 0.0) as total_committed
                    FROM budget_reservations
                    WHERE contract_id = ? 
                      AND status = 'COMMITTED'
                      AND committed_at >= ?
                    """,
                    (contract.contract_id, window_start)
                )
                committed_spent = float(cursor.fetchone()[0])

            # 2. Re-calculate active pending reservations inside lock
            cursor.execute(
                """
                SELECT COALESCE(SUM(amount_inr), 0.0) as total_reserved
                FROM budget_reservations
                WHERE contract_id = ? 
                  AND status = 'PENDING'
                  AND expires_at > ?
                """,
                (contract.contract_id, now_iso)
            )
            active_reserved = float(cursor.fetchone()[0])

            total_budget = contract.max_aggregate_value_inr
            available_budget = total_budget - (committed_spent + active_reserved)

            if amount_inr > available_budget:
                logger.warning(
                    f"Atomic budget reservation denied for contract {contract.contract_id}: "
                    f"Requested ₹{amount_inr:,.2f} > Available ₹{available_budget:,.2f} "
                    f"(Total: ₹{total_budget:,.2f}, Committed: ₹{committed_spent:,.2f}, Reserved: ₹{active_reserved:,.2f})"
                )
                state = BudgetState(
                    total_budget_inr=total_budget,
                    committed_spent_inr=committed_spent,
                    active_reserved_inr=active_reserved,
                    available_budget_inr=round(max(0.0, available_budget), 2),
                    requested_amount_inr=amount_inr,
                    budget_period=contract.budget_period
                )
                return False, None, state

            # Insert atomic reservation
            cursor.execute(
                """
                INSERT INTO budget_reservations (
                    reservation_id, contract_id, decision_id, transaction_id,
                    amount_inr, status, expires_at, created_at
                ) VALUES (?, ?, ?, ?, ?, 'PENDING', ?, ?)
                """,
                (reservation_id, contract.contract_id, decision_id, transaction_id, amount_inr, expires_iso, now_iso)
            )

            new_reserved = active_reserved + amount_inr
            new_available = max(0.0, total_budget - (committed_spent + new_reserved))
            logger.info(
                f"Atomic reservation {reservation_id} created: Reserved ₹{amount_inr:,.2f} on contract {contract.contract_id}. "
                f"New available budget: ₹{new_available:,.2f}"
            )

            state = BudgetState(
                total_budget_inr=total_budget,
                committed_spent_inr=committed_spent,
                active_reserved_inr=new_reserved,
                available_budget_inr=round(new_available, 2),
                requested_amount_inr=amount_inr,
                budget_period=contract.budget_period
            )
            return True, reservation_id, state

    @staticmethod
    def commit_reservation(reservation_id: str) -> bool:
        """Commits a pending budget reservation upon successful payment execution."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with db_transaction() as cursor:
            cursor.execute(
                """
                UPDATE budget_reservations
                SET status = 'COMMITTED', committed_at = ?
                WHERE reservation_id = ? AND status = 'PENDING'
                """,
                (now_iso, reservation_id)
            )
            rows_affected = cursor.rowcount

        if rows_affected > 0:
            logger.info(f"Budget reservation {reservation_id} COMMITTED successfully.")
            return True
        logger.warning(f"Could not commit reservation {reservation_id} (not in PENDING state).")
        return False

    @staticmethod
    def release_reservation(reservation_id: str) -> bool:
        """Releases a pending budget reservation upon payment failure or challenge rejection."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with db_transaction() as cursor:
            cursor.execute(
                """
                UPDATE budget_reservations
                SET status = 'RELEASED', released_at = ?
                WHERE reservation_id = ? AND status = 'PENDING'
                """,
                (now_iso, reservation_id)
            )
            rows_affected = cursor.rowcount

        if rows_affected > 0:
            logger.info(f"Budget reservation {reservation_id} RELEASED successfully.")
            return True
        return False

    @staticmethod
    def get_reservation_by_tx(transaction_id: str) -> Optional[dict]:
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM budget_reservations WHERE transaction_id = ? ORDER BY created_at DESC LIMIT 1",
                (transaction_id,)
            ).fetchone()
            if row:
                return dict(row)
            return None
