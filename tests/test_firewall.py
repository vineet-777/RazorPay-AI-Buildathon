"""Unit tests for Deterministic Authorization Firewall."""

import pytest
from app.authorization.models import CanonicalTransaction, AgentProposal, DecisionEnum
from app.authorization.engine import AuthorizationFirewall


def test_happy_path_grocery_authorization():
    tx = CanonicalTransaction(
        transaction_id="tx_test_happy_01",
        principal_id="user_rahul_sharma",
        agent_id="buyer_agent_01",
        merchant_id="merchant_freshmart",
        sku="GROC-ORGANIC-OATS-1KG",
        category="groceries",
        quantity=2,
        unit_price_inr=349.0,
        subtotal_inr=698.0,
        discount_inr=0.0,
        tax_inr=34.9,
        shipping_inr=50.0,
        total_inr=782.9,
        currency="INR",
        destination_pincode="560001",
        recurring=False,
        timestamp="2026-08-26T12:00:00Z",
        contract_id="contract_grocery_5k_weekly"
    )

    decision = AuthorizationFirewall.evaluate(tx)
    assert decision.decision == DecisionEnum.ALLOW
    assert decision.reason_code == "ALL_CONSTRAINTS_SATISFIED"
    assert len(decision.failed_rules) == 0


def test_single_order_cap_breach():
    tx = CanonicalTransaction(
        transaction_id="tx_test_cap_breach",
        principal_id="user_rahul_sharma",
        agent_id="buyer_agent_01",
        merchant_id="merchant_freshmart",
        sku="GROC-PREMIUM-BASKET",
        category="groceries",
        quantity=1,
        unit_price_inr=3000.0,
        subtotal_inr=3000.0,
        total_inr=3200.0,
        currency="INR",
        destination_pincode="560001",
        recurring=False,
        timestamp="2026-08-26T12:00:00Z",
        contract_id="contract_grocery_5k_weekly"
    )

    decision = AuthorizationFirewall.evaluate(tx)
    assert decision.decision == DecisionEnum.DENY
    assert "RULE_USER_SINGLE_ORDER_CAP" in decision.failed_rules


def test_merchant_substitution_attack():
    proposal = AgentProposal(
        sku="GROC-ORGANIC-OATS-1KG",
        title="Organic Oats",
        merchant_id="merchant_freshmart",
        category="groceries",
        unit_price_inr=349.0,
        quantity=1,
        estimated_total_inr=416.45,
        currency="INR",
        destination_pincode="560001",
        recurring=False
    )
    tx = CanonicalTransaction(
        transaction_id="tx_test_merchant_swap",
        principal_id="user_rahul_sharma",
        agent_id="buyer_agent_01",
        merchant_id="merchant_untrusted",  # Mutated merchant!
        sku="GROC-ORGANIC-OATS-1KG",
        category="groceries",
        quantity=1,
        unit_price_inr=349.0,
        subtotal_inr=349.0,
        total_inr=416.45,
        currency="INR",
        destination_pincode="560001",
        recurring=False,
        timestamp="2026-08-26T12:00:00Z",
        contract_id="contract_grocery_5k_weekly"
    )

    decision = AuthorizationFirewall.evaluate(tx, proposal=proposal)
    assert decision.decision == DecisionEnum.DENY
    assert "RULE_TRANSACTION_MUTATION_MERCHANT" in decision.failed_rules


def test_sku_substitution_challenge():
    proposal = AgentProposal(
        sku="GROC-ALMOND-MILK-1L",
        title="Almond Milk",
        merchant_id="merchant_freshmart",
        category="groceries",
        unit_price_inr=720.0,
        quantity=1,
        estimated_total_inr=806.0,
        currency="INR",
        destination_pincode="560001",
        recurring=False
    )
    tx = CanonicalTransaction(
        transaction_id="tx_test_sku_swap",
        principal_id="user_rahul_sharma",
        agent_id="buyer_agent_01",
        merchant_id="merchant_freshmart",
        sku="GROC-OLIVE-OIL-1L",  # Mutated SKU
        category="groceries",
        quantity=1,
        unit_price_inr=1249.0,
        subtotal_inr=1249.0,
        discount_inr=0.0,
        tax_inr=62.45,
        shipping_inr=50.0,
        total_inr=1361.45,
        currency="INR",
        destination_pincode="560001",
        recurring=False,
        timestamp="2026-08-26T12:00:00Z",
        contract_id="contract_grocery_5k_weekly"
    )

    decision = AuthorizationFirewall.evaluate(tx, proposal=proposal)
    assert decision.decision == DecisionEnum.CHALLENGE
    assert "RULE_TRANSACTION_MUTATION_SKU" in decision.reason_code or len(decision.challenge_reasons) > 0


def test_expired_contract_denial():
    tx = CanonicalTransaction(
        transaction_id="tx_test_expired",
        principal_id="user_rahul_sharma",
        agent_id="buyer_agent_01",
        merchant_id="merchant_freshmart",
        sku="GROC-ORGANIC-OATS-1KG",
        category="groceries",
        quantity=1,
        unit_price_inr=349.0,
        subtotal_inr=349.0,
        total_inr=416.45,
        currency="INR",
        destination_pincode="560001",
        recurring=False,
        timestamp="2026-08-26T12:00:00Z",
        contract_id="contract_expired_demo"
    )

    decision = AuthorizationFirewall.evaluate(tx)
    assert decision.decision == DecisionEnum.DENY
    assert "RULE_USER_CONTRACT_EXPIRY" in decision.failed_rules


def test_revoked_contract_denial():
    tx = CanonicalTransaction(
        transaction_id="tx_test_revoked",
        principal_id="user_priya_patel",
        agent_id="buyer_agent_01",
        merchant_id="merchant_freshmart",
        sku="GROC-ORGANIC-OATS-1KG",
        category="groceries",
        quantity=1,
        unit_price_inr=349.0,
        subtotal_inr=349.0,
        total_inr=416.45,
        currency="INR",
        destination_pincode="560001",
        recurring=False,
        timestamp="2026-08-26T12:00:00Z",
        contract_id="contract_revoked_demo"
    )

    decision = AuthorizationFirewall.evaluate(tx)
    assert decision.decision == DecisionEnum.DENY
    assert "RULE_USER_CONTRACT_REVOCATION" in decision.failed_rules
