"""Concurrency and Atomic Budget Reservation stress tests."""

import threading
import time
import pytest
from app.authorization.contracts import ContractService
from app.authorization.models import CanonicalTransaction, DecisionEnum
from app.authorization.engine import AuthorizationFirewall
from app.authorization.reservations import ReservationService
from app.authorization.budget import BudgetEngine


def test_atomic_concurrency_race_condition():
    """10 simultaneous threads racing for a limited budget. Verifies total spend never exceeds contract limit."""
    contract = ContractService.get_contract("contract_grocery_5k_weekly")
    assert contract is not None

    initial_budget = BudgetEngine.compute_budget_state(contract)
    available = initial_budget.available_budget_inr

    successful_reservations = []
    denied_reservations = []
    lock = threading.Lock()

    def worker(thread_idx: int):
        tx_id = f"test_race_tx_{thread_idx}_{time.time_ns()}"
        tx = CanonicalTransaction(
            transaction_id=tx_id,
            principal_id="user_rahul_sharma",
            agent_id="buyer_agent_01",
            merchant_id="merchant_freshmart",
            sku="GROC-ORGANIC-OATS-1KG",
            category="groceries",
            quantity=3,
            unit_price_inr=349.0,
            subtotal_inr=1047.0,
            discount_inr=0.0,
            tax_inr=52.35,
            shipping_inr=0.0,
            total_inr=1099.35,
            currency="INR",
            destination_pincode="560001",
            recurring=False,
            timestamp="2026-08-26T12:00:00Z",
            contract_id="contract_grocery_5k_weekly"
        )
        decision = AuthorizationFirewall.evaluate(tx)
        with lock:
            if decision.decision == DecisionEnum.ALLOW:
                successful_reservations.append(tx.total_inr)
            else:
                denied_reservations.append(tx.total_inr)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    total_reserved = sum(successful_reservations)
    assert total_reserved <= available
    assert len(successful_reservations) > 0
    assert len(denied_reservations) > 0


def test_reservation_commit_and_release_lifecycle():
    contract = ContractService.get_contract("contract_grocery_5k_weekly")
    assert contract is not None

    ok, res_id, state_1 = ReservationService.atomic_reserve(
        contract=contract,
        amount_inr=1000.0,
        transaction_id="tx_lifecycle_test",
        decision_id="dec_lifecycle_test"
    )
    assert ok is True
    assert res_id is not None

    # Commit reservation
    committed = ReservationService.commit_reservation(res_id)
    assert committed is True

    # Check that committed spent is updated
    state_2 = BudgetEngine.compute_budget_state(contract)
    assert state_2.committed_spent_inr >= 1000.0

    # Test release of another reservation
    ok2, res_id2, _ = ReservationService.atomic_reserve(
        contract=contract,
        amount_inr=500.0,
        transaction_id="tx_lifecycle_test2",
        decision_id="dec_lifecycle_test2"
    )
    assert ok2 is True
    released = ReservationService.release_reservation(res_id2)
    assert released is True
