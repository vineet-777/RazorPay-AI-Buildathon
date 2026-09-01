"""Unit tests for Transaction Mutation Detector."""

from app.authorization.models import CanonicalTransaction, AgentProposal
from app.authorization.mutation import MutationDetector


def test_no_mutation():
    proposal = AgentProposal(
        sku="GROC-ORGANIC-OATS-1KG",
        title="Organic Rolled Oats",
        merchant_id="merchant_freshmart",
        category="groceries",
        unit_price_inr=349.0,
        quantity=2,
        estimated_total_inr=782.9,
        currency="INR",
        destination_pincode="560001",
        recurring=False
    )
    tx = CanonicalTransaction(
        transaction_id="tx_mut_01",
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

    report = MutationDetector.detect_mutations(tx, proposal)
    assert report.has_mutations is False
    assert report.has_material_mutations is False
    assert len(report.differences) == 0


def test_merchant_and_price_mutation():
    proposal = AgentProposal(
        sku="SONY-65X80L-4K",
        title="Sony Bravia 65-inch",
        merchant_id="merchant_croma_store",
        category="electronics",
        unit_price_inr=68999.0,
        quantity=1,
        estimated_total_inr=68999.0,
        currency="INR",
        destination_pincode="560001",
        recurring=False
    )
    tx = CanonicalTransaction(
        transaction_id="tx_mut_02",
        principal_id="user_238",
        agent_id="buyer_agent_01",
        merchant_id="merchant_untrusted",  # Mutated
        sku="SONY-65X80L-4K",
        category="electronics",
        quantity=1,
        unit_price_inr=74999.0,  # Mutated price
        subtotal_inr=74999.0,
        total_inr=74999.0,
        currency="INR",
        destination_pincode="560001",
        recurring=False,
        timestamp="2026-08-26T12:00:00Z",
        contract_id="contract_tv_electronics_75k"
    )

    report = MutationDetector.detect_mutations(tx, proposal)
    assert report.has_mutations is True
    assert report.has_material_mutations is True
    fields = [d.field for d in report.differences]
    assert "merchant_id" in fields
    assert "total_inr" in fields
