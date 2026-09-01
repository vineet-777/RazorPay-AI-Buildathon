"""Merchant AI Policy Engine & Versioning Manager."""

import json
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from app.core.db import get_db, db_transaction
from app.commerce.models import MerchantPolicy
from app.core.logging import logger

SEED_POLICIES: List[Dict[str, Any]] = [
    # FreshMart default policy v1
    {
        "merchant_id": "merchant_freshmart",
        "version": "v1",
        "ai_sales_enabled": True,
        "max_ai_order_value_inr": 5000.0,
        "allowed_categories": ["groceries", "personal_care"],
        "allow_quantity_changes": True,
        "allow_substitutions": False,
        "allow_discounts": True,
        "max_discount_pct": 10.0,
        "require_step_up_rules": ["new_customer", "high_value_order", "product_substitution"],
        "is_active": True
    },
    # Croma Digital Electronics historical policy v14 (allows 65-inch TV under ₹75,000 autonomously)
    {
        "merchant_id": "merchant_croma_store",
        "version": "v14",
        "ai_sales_enabled": True,
        "max_ai_order_value_inr": 75000.0,
        "allowed_categories": ["electronics", "home_appliances"],
        "allow_quantity_changes": False,
        "allow_substitutions": False,
        "allow_discounts": True,
        "max_discount_pct": 5.0,
        "require_step_up_rules": ["new_customer", "product_substitution"],
        "is_active": False  # Superseded by v15 for replay testing
    },
    # Croma Digital Electronics strict active policy v15 (lowers autonomous ceiling to ₹50,000 -> CHALLENGES ₹68,999 TV!)
    {
        "merchant_id": "merchant_croma_store",
        "version": "v15",
        "ai_sales_enabled": True,
        "max_ai_order_value_inr": 50000.0,
        "allowed_categories": ["electronics", "home_appliances"],
        "allow_quantity_changes": False,
        "allow_substitutions": False,
        "allow_discounts": True,
        "max_discount_pct": 5.0,
        "require_step_up_rules": ["new_customer", "high_value_order", "product_substitution"],
        "is_active": True
    },
    # Apothecary policy v1
    {
        "merchant_id": "merchant_apothecary",
        "version": "v1",
        "ai_sales_enabled": True,
        "max_ai_order_value_inr": 3000.0,
        "allowed_categories": ["personal_care", "pharmacy"],
        "allow_quantity_changes": True,
        "allow_substitutions": True,
        "allow_discounts": True,
        "max_discount_pct": 15.0,
        "require_step_up_rules": ["prescription_required"],
        "is_active": True
    },
    # QuickDash policy v1
    {
        "merchant_id": "merchant_quickdash",
        "version": "v1",
        "ai_sales_enabled": True,
        "max_ai_order_value_inr": 2000.0,
        "allowed_categories": ["groceries", "snacks"],
        "allow_quantity_changes": True,
        "allow_substitutions": False,
        "allow_discounts": True,
        "max_discount_pct": 10.0,
        "require_step_up_rules": [],
        "is_active": True
    },
    # Untrusted / AI Disabled Merchant Policy v1
    {
        "merchant_id": "merchant_untrusted",
        "version": "v1",
        "ai_sales_enabled": False,  # AI Disabled!
        "max_ai_order_value_inr": 0.0,
        "allowed_categories": [],
        "allow_quantity_changes": False,
        "allow_substitutions": False,
        "allow_discounts": False,
        "max_discount_pct": 0.0,
        "require_step_up_rules": ["all_transactions"],
        "is_active": True
    }
]


class MerchantPolicyService:
    @staticmethod
    def seed_policies() -> None:
        """Seeds default versioned merchant policies into the database."""
        with db_transaction() as cursor:
            now = datetime.now(timezone.utc).isoformat()
            for p in SEED_POLICIES:
                cursor.execute(
                    """
                    INSERT INTO merchant_policies (
                        merchant_id, version, ai_sales_enabled, max_ai_order_value_inr,
                        allowed_categories, allow_quantity_changes, allow_substitutions,
                        allow_discounts, max_discount_pct, require_step_up_rules,
                        is_active, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(merchant_id, version) DO UPDATE SET
                        ai_sales_enabled=excluded.ai_sales_enabled,
                        max_ai_order_value_inr=excluded.max_ai_order_value_inr,
                        allowed_categories=excluded.allowed_categories,
                        allow_quantity_changes=excluded.allow_quantity_changes,
                        allow_substitutions=excluded.allow_substitutions,
                        allow_discounts=excluded.allow_discounts,
                        max_discount_pct=excluded.max_discount_pct,
                        require_step_up_rules=excluded.require_step_up_rules,
                        is_active=excluded.is_active
                    """,
                    (
                        p["merchant_id"], p["version"],
                        1 if p["ai_sales_enabled"] else 0,
                        p["max_ai_order_value_inr"],
                        json.dumps(p["allowed_categories"]),
                        1 if p["allow_quantity_changes"] else 0,
                        1 if p["allow_substitutions"] else 0,
                        1 if p["allow_discounts"] else 0,
                        p["max_discount_pct"],
                        json.dumps(p["require_step_up_rules"]),
                        1 if p["is_active"] else 0,
                        now
                    )
                )
        logger.info("Merchant AI policies seeded successfully.")

    @staticmethod
    def get_active_policy(merchant_id: str) -> Optional[MerchantPolicy]:
        """Retrieves the current active policy for a merchant."""
        with get_db() as conn:
            row = conn.execute(
                """
                SELECT * FROM merchant_policies 
                WHERE merchant_id = ? AND is_active = 1 
                ORDER BY id DESC LIMIT 1
                """,
                (merchant_id,)
            ).fetchone()
            if not row:
                return None
            return MerchantPolicyService._row_to_policy(row)

    @staticmethod
    def get_policy_by_version(merchant_id: str, version: str) -> Optional[MerchantPolicy]:
        """Retrieves a specific policy version for replay and forensics."""
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM merchant_policies WHERE merchant_id = ? AND version = ?",
                (merchant_id, version)
            ).fetchone()
            if not row:
                return None
            return MerchantPolicyService._row_to_policy(row)

    @staticmethod
    def list_policies_for_merchant(merchant_id: str) -> List[MerchantPolicy]:
        """Lists all historical and active policies for a merchant."""
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM merchant_policies WHERE merchant_id = ? ORDER BY id DESC",
                (merchant_id,)
            ).fetchall()
            return [MerchantPolicyService._row_to_policy(r) for r in rows]

    @staticmethod
    def create_policy_version(policy: MerchantPolicy) -> MerchantPolicy:
        """Creates a new policy version and optionally makes it active."""
        with db_transaction() as cursor:
            now = datetime.now(timezone.utc).isoformat()
            if policy.is_active:
                cursor.execute(
                    "UPDATE merchant_policies SET is_active = 0 WHERE merchant_id = ?",
                    (policy.merchant_id,)
                )

            cursor.execute(
                """
                INSERT INTO merchant_policies (
                    merchant_id, version, ai_sales_enabled, max_ai_order_value_inr,
                    allowed_categories, allow_quantity_changes, allow_substitutions,
                    allow_discounts, max_discount_pct, require_step_up_rules,
                    is_active, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    policy.merchant_id, policy.version,
                    1 if policy.ai_sales_enabled else 0,
                    policy.max_ai_order_value_inr,
                    json.dumps(policy.allowed_categories),
                    1 if policy.allow_quantity_changes else 0,
                    1 if policy.allow_substitutions else 0,
                    1 if policy.allow_discounts else 0,
                    policy.max_discount_pct,
                    json.dumps(policy.require_step_up_rules),
                    1 if policy.is_active else 0,
                    now
                )
            )
        logger.info(f"Created merchant policy version {policy.version} for {policy.merchant_id}")
        return policy

    @staticmethod
    def _row_to_policy(row: Any) -> MerchantPolicy:
        allowed_categories = []
        require_step_up_rules = []
        try:
            allowed_categories = json.loads(row["allowed_categories"])
        except Exception:
            pass
        try:
            require_step_up_rules = json.loads(row["require_step_up_rules"])
        except Exception:
            pass

        return MerchantPolicy(
            merchant_id=row["merchant_id"],
            version=row["version"],
            ai_sales_enabled=bool(row["ai_sales_enabled"]),
            max_ai_order_value_inr=float(row["max_ai_order_value_inr"]),
            allowed_categories=allowed_categories,
            allow_quantity_changes=bool(row["allow_quantity_changes"]),
            allow_substitutions=bool(row["allow_substitutions"]),
            allow_discounts=bool(row["allow_discounts"]),
            max_discount_pct=float(row["max_discount_pct"]),
            require_step_up_rules=require_step_up_rules,
            is_active=bool(row["is_active"]),
            created_at=row["created_at"]
        )
