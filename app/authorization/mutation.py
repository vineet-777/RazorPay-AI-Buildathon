"""Material Transaction Mutation Detector."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.authorization.models import CanonicalTransaction, AgentProposal


class MutationDifference(BaseModel):
    field: str
    proposed_value: Any
    executable_value: Any
    is_material: bool
    description: str


class MutationReport(BaseModel):
    has_mutations: bool
    has_material_mutations: bool
    differences: List[MutationDifference] = Field(default_factory=list)


class MutationDetector:
    """Detects material differences between an agent's proposed intent and final executable transaction facts."""

    @staticmethod
    def detect_mutations(tx: CanonicalTransaction, proposal: Optional[AgentProposal]) -> MutationReport:
        if not proposal:
            return MutationReport(has_mutations=False, has_material_mutations=False, differences=[])

        diffs: List[MutationDifference] = []

        # 1. Merchant Mutation
        if tx.merchant_id != proposal.merchant_id:
            diffs.append(
                MutationDifference(
                    field="merchant_id",
                    proposed_value=proposal.merchant_id,
                    executable_value=tx.merchant_id,
                    is_material=True,
                    description=f"Merchant mutated from '{proposal.merchant_id}' to '{tx.merchant_id}'."
                )
            )

        # 2. SKU Mutation
        if tx.sku != proposal.sku:
            diffs.append(
                MutationDifference(
                    field="sku",
                    proposed_value=proposal.sku,
                    executable_value=tx.sku,
                    is_material=True,
                    description=f"Product SKU mutated from '{proposal.sku}' to '{tx.sku}'."
                )
            )

        # 3. Category Mutation
        if tx.category != proposal.category:
            diffs.append(
                MutationDifference(
                    field="category",
                    proposed_value=proposal.category,
                    executable_value=tx.category,
                    is_material=True,
                    description=f"Product category mutated from '{proposal.category}' to '{tx.category}'."
                )
            )

        # 4. Quantity Mutation
        if tx.quantity != proposal.quantity:
            diffs.append(
                MutationDifference(
                    field="quantity",
                    proposed_value=proposal.quantity,
                    executable_value=tx.quantity,
                    is_material=True,
                    description=f"Quantity changed from {proposal.quantity} to {tx.quantity}."
                )
            )

        # 5. Price Drift Mutation
        drift_inr = round(tx.total_inr - proposal.estimated_total_inr, 2)
        drift_pct = round((drift_inr / max(proposal.estimated_total_inr, 1.0)) * 100.0, 2)
        if abs(drift_inr) > 0.05:
            is_material = drift_pct > 5.0 or drift_inr > 200.0
            diffs.append(
                MutationDifference(
                    field="total_inr",
                    proposed_value=proposal.estimated_total_inr,
                    executable_value=tx.total_inr,
                    is_material=is_material,
                    description=f"Total amount drifted by ₹{drift_inr:,.2f} ({drift_pct:+0.2f}% change)."
                )
            )

        # 6. Recurring Subscription Mutation
        if tx.recurring != proposal.recurring:
            diffs.append(
                MutationDifference(
                    field="recurring",
                    proposed_value=proposal.recurring,
                    executable_value=tx.recurring,
                    is_material=True,
                    description=f"Payment recurring mode mutated from {proposal.recurring} to {tx.recurring}."
                )
            )

        # 7. Destination Pincode Mutation
        if proposal.destination_pincode and tx.destination_pincode and proposal.destination_pincode != tx.destination_pincode:
            diffs.append(
                MutationDifference(
                    field="destination_pincode",
                    proposed_value=proposal.destination_pincode,
                    executable_value=tx.destination_pincode,
                    is_material=True,
                    description=f"Destination pincode mutated from '{proposal.destination_pincode}' to '{tx.destination_pincode}'."
                )
            )

        has_material = any(d.is_material for d in diffs)
        return MutationReport(
            has_mutations=len(diffs) > 0,
            has_material_mutations=has_material,
            differences=diffs
        )
