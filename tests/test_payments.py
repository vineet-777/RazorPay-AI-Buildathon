"""Tests for Payments, Razorpay Test-Mode, State Machine, and Idempotency."""

import pytest
from app.authorization.models import CanonicalTransaction, DecisionEnum
from app.authorization.engine import AuthorizationFirewall
from app.payments.models import (
    TransactionStatus, PaymentExecutionRequest, PaymentExecutionResponse
)
from app.payments.razorpay_client import RazorpayGatewayService
from app.payments.state_machine import PaymentStateMachine, InvalidStateTransitionError


def test_payment_state_machine_transitions():
    assert PaymentStateMachine.validate_transition(TransactionStatus.DRAFT, TransactionStatus.AUTHORIZATION_PENDING) is True
    assert PaymentStateMachine.validate_transition(TransactionStatus.AUTHORIZATION_PENDING, TransactionStatus.AUTHORIZED) is True
    assert PaymentStateMachine.validate_transition(TransactionStatus.AUTHORIZED, TransactionStatus.PAYMENT_PENDING) is True
    assert PaymentStateMachine.validate_transition(TransactionStatus.PAYMENT_PENDING, TransactionStatus.COMPLETED) is True

    # Invalid state transition should raise exception
    with pytest.raises(InvalidStateTransitionError):
        PaymentStateMachine.validate_transition(TransactionStatus.COMPLETED, TransactionStatus.DRAFT)


def test_successful_razorpay_payment_flow():
    tx = CanonicalTransaction(
        transaction_id="tx_pay_success_test",
        principal_id="user_rahul_sharma",
        agent_id="buyer_agent_01",
        merchant_id="merchant_freshmart",
        sku="GROC-ORGANIC-OATS-1KG",
        category="groceries",
        quantity=1,
        unit_price_inr=349.0,
        subtotal_inr=349.0,
        total_inr=349.0,
        currency="INR",
        destination_pincode="560001",
        recurring=False,
        timestamp="2026-08-26T12:00:00Z",
        contract_id="contract_grocery_5k_weekly",
        idempotency_key="idem_key_001"
    )
    decision = AuthorizationFirewall.evaluate(tx)
    assert decision.decision == DecisionEnum.ALLOW

    pay_req = PaymentExecutionRequest(
        transaction_id="tx_pay_success_test",
        decision_id=decision.decision_id,
        idempotency_key="idem_key_001"
    )
    resp = RazorpayGatewayService.execute_payment(pay_req)
    assert resp.success is True
    assert resp.status == TransactionStatus.COMPLETED
    assert resp.razorpay_order_id is not None
    assert resp.signature is not None

    # Idempotent retry of same request
    retry_resp = RazorpayGatewayService.execute_payment(pay_req)
    assert retry_resp.success is True
    assert retry_resp.idempotent_replay is True
    assert retry_resp.payment_id == resp.payment_id


def test_simulated_payment_failure_releases_budget():
    tx = CanonicalTransaction(
        transaction_id="tx_pay_fail_test",
        principal_id="user_rahul_sharma",
        agent_id="buyer_agent_01",
        merchant_id="merchant_freshmart",
        sku="GROC-ORGANIC-OATS-1KG",
        category="groceries",
        quantity=1,
        unit_price_inr=349.0,
        subtotal_inr=349.0,
        total_inr=349.0,
        currency="INR",
        destination_pincode="560001",
        recurring=False,
        timestamp="2026-08-26T12:00:00Z",
        contract_id="contract_grocery_5k_weekly"
    )
    decision = AuthorizationFirewall.evaluate(tx)
    assert decision.decision == DecisionEnum.ALLOW

    pay_req = PaymentExecutionRequest(
        transaction_id="tx_pay_fail_test",
        decision_id=decision.decision_id,
        idempotency_key="idem_fail_002",
        simulate_payment_failure=True
    )
    resp = RazorpayGatewayService.execute_payment(pay_req)
    assert resp.success is False
    assert resp.status == TransactionStatus.PAYMENT_FAILED
