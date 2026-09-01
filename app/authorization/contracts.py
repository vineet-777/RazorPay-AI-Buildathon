"""User Authorization Contracts Service and Schema."""

import json
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from app.core.db import get_db, db_transaction
from app.core.logging import logger


class UserAuthorizationContract(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    contract_id: str
    principal_id: str
    agent_id: str
    version: int = 1
    merchants_allowlist: List[str] = Field(default_factory=list)
    categories_allowlist: List[str] = Field(default_factory=list)
    max_order_value_inr: float = Field(..., ge=0)
    max_aggregate_value_inr: float = Field(..., ge=0)
    budget_period: str = Field(default="weekly")
    recurring_allowed: bool = False
    delivery_pincodes: List[str] = Field(default_factory=list)
    approval_conditions: List[str] = Field(
        default_factory=lambda: ["new_merchant", "price_increase_over_10_percent", "substituted_sku", "unapproved_pincode"]
    )
    issued_at: str
    expires_at: str
    is_revoked: bool = False
    raw_natural_language: Optional[str] = None
    created_at: Optional[str] = None


SEED_USERS = [
    {"user_id": "user_rahul_sharma", "name": "Rahul Sharma", "email": "rahul.sharma@example.com"},
    {"user_id": "user_priya_patel", "name": "Priya Patel", "email": "priya.patel@example.com"},
    {"user_id": "user_238", "name": "Demo User 238", "email": "demo238@example.com"},
]

SEED_CONTRACTS = [
    # Contract 1: Grocery Weekly Budget (Active, Valid)
    {
        "contract_id": "contract_grocery_5k_weekly",
        "principal_id": "user_rahul_sharma",
        "agent_id": "buyer_agent_01",
        "version": 1,
        "merchants_allowlist": ["merchant_freshmart", "merchant_quickdash"],
        "categories_allowlist": ["groceries", "personal_care"],
        "max_order_value_inr": 2500.0,
        "max_aggregate_value_inr": 5000.0,
        "budget_period": "weekly",
        "recurring_allowed": False,
        "delivery_pincodes": ["560001", "560002", "560034", "560095"],
        "approval_conditions": ["new_merchant", "price_increase_over_10_percent", "substituted_sku", "unapproved_pincode"],
        "days_valid": 7,
        "is_revoked": False,
        "raw_natural_language": "You can spend up to ₹5,000 this week on groceries and personal care from FreshMart or QuickDash. Max ₹2,500 per order. Ask me before substitutions or recurring purchases."
    },
    # Contract 2: Electronics Ceiling (Active, Valid)
    {
        "contract_id": "contract_tv_electronics_75k",
        "principal_id": "user_238",
        "agent_id": "buyer_agent_01",
        "version": 1,
        "merchants_allowlist": ["merchant_croma_store"],
        "categories_allowlist": ["electronics"],
        "max_order_value_inr": 75000.0,
        "max_aggregate_value_inr": 75000.0,
        "budget_period": "per_order",
        "recurring_allowed": False,
        "delivery_pincodes": ["560001", "560008", "560025"],
        "approval_conditions": ["new_merchant", "price_increase_over_10_percent", "substituted_sku"],
        "days_valid": 14,
        "is_revoked": False,
        "raw_natural_language": "Find me a 65-inch 4K TV under ₹70,000. Prefer Sony or LG. Deliver to Bangalore. You can spend up to ₹75,000 if there's free installation."
    },
    # Contract 2b: Electronics Ceiling for Replay Testing
    {
        "contract_id": "contract_tv_electronics_replay_v15",
        "principal_id": "user_238",
        "agent_id": "buyer_agent_01",
        "version": 1,
        "merchants_allowlist": ["merchant_croma_store"],
        "categories_allowlist": ["electronics"],
        "max_order_value_inr": 75000.0,
        "max_aggregate_value_inr": 75000.0,
        "budget_period": "per_order",
        "recurring_allowed": False,
        "delivery_pincodes": ["560001", "560008", "560025"],
        "approval_conditions": ["new_merchant", "price_increase_over_10_percent", "substituted_sku"],
        "days_valid": 14,
        "is_revoked": False,
        "raw_natural_language": "Replay test contract."
    },
    # Contract 3: Expired Delegation
    {
        "contract_id": "contract_expired_demo",
        "principal_id": "user_rahul_sharma",
        "agent_id": "buyer_agent_01",
        "version": 1,
        "merchants_allowlist": ["merchant_freshmart"],
        "categories_allowlist": ["groceries"],
        "max_order_value_inr": 1500.0,
        "max_aggregate_value_inr": 3000.0,
        "budget_period": "weekly",
        "recurring_allowed": False,
        "delivery_pincodes": ["560001"],
        "approval_conditions": ["new_merchant"],
        "days_valid": -3,  # Expired 3 days ago!
        "is_revoked": False,
        "raw_natural_language": "Temporary authority that expired 3 days ago."
    },
    # Contract 4: Revoked Delegation
    {
        "contract_id": "contract_revoked_demo",
        "principal_id": "user_priya_patel",
        "agent_id": "buyer_agent_01",
        "version": 1,
        "merchants_allowlist": ["merchant_freshmart", "merchant_croma_store"],
        "categories_allowlist": ["groceries", "electronics"],
        "max_order_value_inr": 10000.0,
        "max_aggregate_value_inr": 20000.0,
        "budget_period": "weekly",
        "recurring_allowed": False,
        "delivery_pincodes": ["560001"],
        "approval_conditions": ["new_merchant"],
        "days_valid": 7,
        "is_revoked": True,  # Revoked by user!
        "raw_natural_language": "Revoked authority contract for testing revocation defenses."
    }
]


class ContractService:
    @staticmethod
    def seed_contracts() -> None:
        """Seeds initial demo users and contracts."""
        with db_transaction() as cursor:
            now = datetime.now(timezone.utc)
            now_iso = now.isoformat()

            # Seed Users
            for u in SEED_USERS:
                cursor.execute(
                    """
                    INSERT INTO users (user_id, name, email, created_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET name=excluded.name, email=excluded.email
                    """,
                    (u["user_id"], u["name"], u["email"], now_iso)
                )

            # Seed Contracts
            for c in SEED_CONTRACTS:
                issued = now
                expires = now + timedelta(days=c["days_valid"])
                cursor.execute(
                    """
                    INSERT INTO authorization_contracts (
                        contract_id, principal_id, agent_id, version,
                        merchants_allowlist, categories_allowlist, max_order_value_inr,
                        max_aggregate_value_inr, budget_period, recurring_allowed,
                        delivery_pincodes, approval_conditions, issued_at, expires_at,
                        is_revoked, raw_natural_language, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(contract_id) DO UPDATE SET
                        version=excluded.version,
                        merchants_allowlist=excluded.merchants_allowlist,
                        categories_allowlist=excluded.categories_allowlist,
                        max_order_value_inr=excluded.max_order_value_inr,
                        max_aggregate_value_inr=excluded.max_aggregate_value_inr,
                        budget_period=excluded.budget_period,
                        recurring_allowed=excluded.recurring_allowed,
                        delivery_pincodes=excluded.delivery_pincodes,
                        approval_conditions=excluded.approval_conditions,
                        issued_at=excluded.issued_at,
                        expires_at=excluded.expires_at,
                        is_revoked=excluded.is_revoked,
                        raw_natural_language=excluded.raw_natural_language
                    """,
                    (
                        c["contract_id"], c["principal_id"], c["agent_id"], c["version"],
                        json.dumps(c["merchants_allowlist"]),
                        json.dumps(c["categories_allowlist"]),
                        c["max_order_value_inr"],
                        c["max_aggregate_value_inr"],
                        c["budget_period"],
                        1 if c["recurring_allowed"] else 0,
                        json.dumps(c["delivery_pincodes"]),
                        json.dumps(c["approval_conditions"]),
                        issued.isoformat(),
                        expires.isoformat(),
                        1 if c["is_revoked"] else 0,
                        c["raw_natural_language"],
                        now_iso
                    )
                )
        logger.info("User authorization contracts seeded successfully.")

    @staticmethod
    def get_contract(contract_id: str) -> Optional[UserAuthorizationContract]:
        """Fetches an authorization contract by contract_id."""
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM authorization_contracts WHERE contract_id = ?",
                (contract_id,)
            ).fetchone()
            if not row:
                return None
            return ContractService._row_to_contract(row)

    @staticmethod
    def list_contracts_for_principal(principal_id: str) -> List[UserAuthorizationContract]:
        """Lists all contracts for a user/principal."""
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM authorization_contracts WHERE principal_id = ? ORDER BY created_at DESC",
                (principal_id,)
            ).fetchall()
            return [ContractService._row_to_contract(r) for r in rows]

    @staticmethod
    def create_contract(contract: UserAuthorizationContract) -> UserAuthorizationContract:
        """Persists a new user authorization contract."""
        with db_transaction() as cursor:
            now_iso = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                """
                INSERT INTO authorization_contracts (
                    contract_id, principal_id, agent_id, version,
                    merchants_allowlist, categories_allowlist, max_order_value_inr,
                    max_aggregate_value_inr, budget_period, recurring_allowed,
                    delivery_pincodes, approval_conditions, issued_at, expires_at,
                    is_revoked, raw_natural_language, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    contract.contract_id, contract.principal_id, contract.agent_id, contract.version,
                    json.dumps(contract.merchants_allowlist),
                    json.dumps(contract.categories_allowlist),
                    contract.max_order_value_inr,
                    contract.max_aggregate_value_inr,
                    contract.budget_period,
                    1 if contract.recurring_allowed else 0,
                    json.dumps(contract.delivery_pincodes),
                    json.dumps(contract.approval_conditions),
                    contract.issued_at,
                    contract.expires_at,
                    1 if contract.is_revoked else 0,
                    contract.raw_natural_language,
                    now_iso
                )
            )
        logger.info(f"Created authorization contract {contract.contract_id} for {contract.principal_id}")
        return contract

    @staticmethod
    def revoke_contract(contract_id: str) -> bool:
        """Revokes an authorization contract immediately."""
        with db_transaction() as cursor:
            cursor.execute(
                "UPDATE authorization_contracts SET is_revoked = 1 WHERE contract_id = ?",
                (contract_id,)
            )
        logger.info(f"Revoked authorization contract {contract_id}")
        return True

    @staticmethod
    def _row_to_contract(row: Any) -> UserAuthorizationContract:
        merchants_allowlist = []
        categories_allowlist = []
        delivery_pincodes = []
        approval_conditions = []
        try:
            merchants_allowlist = json.loads(row["merchants_allowlist"])
        except Exception:
            pass
        try:
            categories_allowlist = json.loads(row["categories_allowlist"])
        except Exception:
            pass
        try:
            delivery_pincodes = json.loads(row["delivery_pincodes"])
        except Exception:
            pass
        try:
            approval_conditions = json.loads(row["approval_conditions"])
        except Exception:
            pass

        return UserAuthorizationContract(
            contract_id=row["contract_id"],
            principal_id=row["principal_id"],
            agent_id=row["agent_id"],
            version=int(row["version"]),
            merchants_allowlist=merchants_allowlist,
            categories_allowlist=categories_allowlist,
            max_order_value_inr=float(row["max_order_value_inr"]),
            max_aggregate_value_inr=float(row["max_aggregate_value_inr"]),
            budget_period=row["budget_period"],
            recurring_allowed=bool(row["recurring_allowed"]),
            delivery_pincodes=delivery_pincodes,
            approval_conditions=approval_conditions,
            issued_at=row["issued_at"],
            expires_at=row["expires_at"],
            is_revoked=bool(row["is_revoked"]),
            raw_natural_language=row["raw_natural_language"],
            created_at=row["created_at"]
        )
