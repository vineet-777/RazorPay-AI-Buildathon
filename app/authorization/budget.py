"""Budget calculation and aggregation engine."""

from datetime import datetime, timezone, timedelta
from typing import Tuple
from app.core.db import get_db
from app.authorization.models import BudgetState
from app.authorization.contracts import UserAuthorizationContract
from app.core.logging import logger


class BudgetEngine:
    @staticmethod
    def get_budget_window_start(contract: UserAuthorizationContract) -> str:
        """Calculates the start timestamp of the current budget period window."""
        now = datetime.now(timezone.utc)
        period = contract.budget_period.lower()

        if period == "daily":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "weekly":
            # Start of current week (Monday)
            start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "monthly":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif period == "per_order":
            # Per order means aggregate is checked per individual order lifecycle
            return "1970-01-01T00:00:00+00:00"
        else:  # lifetime or default
            return contract.issued_at

        return start.isoformat()

    @staticmethod
    def compute_budget_state(contract: UserAuthorizationContract, requested_amount: float = 0.0) -> BudgetState:
        """Computes current committed spent and active pending reservations under the contract."""
        window_start = BudgetEngine.get_budget_window_start(contract)
        now_iso = datetime.now(timezone.utc).isoformat()

        is_per_order = (contract.budget_period.lower() == "per_order")

        with get_db() as conn:
            # 1. Committed spending in active window (0 for per_order)
            committed_spent = 0.0
            if not is_per_order:
                committed_row = conn.execute(
                    """
                    SELECT COALESCE(SUM(amount_inr), 0.0) as total_committed
                    FROM budget_reservations
                    WHERE contract_id = ? 
                      AND status = 'COMMITTED'
                      AND committed_at >= ?
                    """,
                    (contract.contract_id, window_start)
                ).fetchone()
                committed_spent = float(committed_row["total_committed"]) if committed_row else 0.0

            # 2. Active, unexpired pending reservations
            reserved_row = conn.execute(
                """
                SELECT COALESCE(SUM(amount_inr), 0.0) as total_reserved
                FROM budget_reservations
                WHERE contract_id = ? 
                  AND status = 'PENDING'
                  AND expires_at > ?
                """,
                (contract.contract_id, now_iso)
            ).fetchone()
            active_reserved = float(reserved_row["total_reserved"]) if reserved_row else 0.0

        total_budget = contract.max_aggregate_value_inr
        available_budget = max(0.0, total_budget - (committed_spent + active_reserved))

        return BudgetState(
            total_budget_inr=total_budget,
            committed_spent_inr=committed_spent,
            active_reserved_inr=active_reserved,
            available_budget_inr=round(available_budget, 2),
            requested_amount_inr=requested_amount,
            budget_period=contract.budget_period
        )
