"""End-to-End Integration and API tests for Agent Commerce Gateway."""

import pytest
from starlette.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["razorpay_mode"] == "TEST_MODE"


def test_catalog_discovery_api():
    resp = client.get("/api/v1/commerce/catalog?category=groceries")
    assert resp.status_code == 200
    products = resp.json()
    assert len(products) > 0
    assert all(p["category"] == "groceries" for p in products)


def test_structured_negotiation_api():
    payload = {
        "product_category": "groceries",
        "preferred_sku": "GROC-PREMIUM-BASKET",
        "target_budget_inr": 2300.0,
        "hard_ceiling_inr": 2600.0,
        "installation_required": False,
        "requested_quantity": 1
    }
    resp = client.post("/api/v1/commerce/negotiate?merchant_id=merchant_freshmart", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["eligible"] is True
    assert data["sku"] == "GROC-PREMIUM-BASKET"
    assert data["offered_price_inr"] <= 2500.0


def test_policy_compiler_api():
    payload = {
        "principal_id": "user_rahul_sharma",
        "agent_id": "buyer_agent_01",
        "natural_language_prompt": "Spend up to ₹3,000 this week on groceries from FreshMart."
    }
    resp = client.post("/api/v1/user/delegations/compile", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["requires_confirmation"] is True  # Ambiguity detection triggered
    assert len(data["ambiguities"]) > 0


def test_end_to_end_ai_buyer_shopping_workflow():
    payload = {
        "user_id": "user_rahul_sharma",
        "contract_id": "contract_grocery_5k_weekly",
        "goal": "Buy organic rolled oats from FreshMart under ₹1,000",
        "target_budget_inr": 800.0,
        "hard_ceiling_inr": 1000.0,
        "preferred_category": "groceries",
        "destination_pincode": "560001",
        "requested_quantity": 1,
        "execute_payment_if_allowed": True
    }
    resp = client.post("/api/v1/agent/shop", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ALLOW"
    assert data["selected_product"]["sku"] == "GROC-ORGANIC-OATS-1KG"
    assert data["authorization_decision"] is not None
    assert data["payment_response"] is not None
    assert data["payment_response"]["success"] is True
    assert data["payment_response"]["status"] == "COMPLETED"


def test_forensic_replay_api():
    # 1. Execute an authorization decision first
    tx_payload = {
        "canonical_transaction": {
            "transaction_id": "tx_replay_api_test",
            "principal_id": "user_238",
            "agent_id": "buyer_agent_01",
            "merchant_id": "merchant_croma_store",
            "sku": "SONY-65X80L-4K",
            "category": "electronics",
            "quantity": 1,
            "unit_price_inr": 68999.0,
            "subtotal_inr": 68999.0,
            "total_inr": 68999.0,
            "currency": "INR",
            "destination_pincode": "560001",
            "recurring": False,
            "timestamp": "2026-08-26T12:00:00Z",
            "contract_id": "contract_tv_electronics_replay_v15",
            "merchant_policy_version": "v14"
        }
    }
    auth_resp = client.post("/api/v1/gateway/authorize", json=tx_payload)
    assert auth_resp.status_code == 200
    decision = auth_resp.json()
    assert decision["decision"] == "ALLOW"

    # 2. Replay under policy v15 (which lowered autonomous ceiling to ₹50,000)
    replay_payload = {
        "decision_id": decision["decision_id"],
        "target_merchant_policy_version": "v15"
    }
    replay_resp = client.post("/api/v1/audit/replay", json=replay_payload)
    assert replay_resp.status_code == 200
    rep_data = replay_resp.json()
    assert rep_data["historical_decision"] == "ALLOW"
    assert rep_data["replayed_decision"] == "CHALLENGE"
    assert rep_data["is_decision_identical"] is False
