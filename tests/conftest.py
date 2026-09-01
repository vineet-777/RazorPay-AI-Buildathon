"""Pytest test fixtures and configuration."""

import pytest
from app.core.db import init_db, db_transaction
from app.commerce.catalog import CatalogService
from app.commerce.merchant_policy import MerchantPolicyService
from app.authorization.contracts import ContractService


@pytest.fixture(autouse=True)
def reset_database():
    """Resets and reseeds database tables cleanly before each test function."""
    init_db()
    with db_transaction() as cursor:
        cursor.execute("PRAGMA foreign_keys = OFF;")
        cursor.execute("DELETE FROM payment_attempts;")
        cursor.execute("DELETE FROM transactions;")
        cursor.execute("DELETE FROM step_up_challenges;")
        cursor.execute("DELETE FROM budget_reservations;")
        cursor.execute("DELETE FROM authorization_decisions;")
        cursor.execute("DELETE FROM audit_events;")
        cursor.execute("DELETE FROM authorization_contracts;")
        cursor.execute("DELETE FROM products;")
        cursor.execute("DELETE FROM merchant_policies;")
        cursor.execute("DELETE FROM merchants;")
        cursor.execute("DELETE FROM users;")
        cursor.execute("PRAGMA foreign_keys = ON;")

    CatalogService.seed_catalog()
    MerchantPolicyService.seed_policies()
    ContractService.seed_contracts()
    yield
