"""Database connection manager and schema initialization for Agent Commerce Gateway."""

import sqlite3
import os
import threading
from contextlib import contextmanager
from typing import Generator
from app.core.config import settings
from app.core.logging import logger

# Thread-local storage for SQLite connections
_local = threading.local()
_db_lock = threading.Lock()


def get_db_path() -> str:
    db_url = settings.DATABASE_URL
    if db_url.startswith("sqlite:///"):
        return db_url.replace("sqlite:///", "")
    return "agent_commerce.db"


def get_db_connection() -> sqlite3.Connection:
    """Returns a thread-local SQLite connection configured with WAL and foreign keys."""
    if not hasattr(_local, "conn") or _local.conn is None:
        db_path = get_db_path()
        conn = sqlite3.connect(
            db_path,
            timeout=30.0,
            check_same_thread=False,
            isolation_level=None  # Enable autocommit mode / explicit transaction management
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA busy_timeout=30000;")
        _local.conn = conn
    return _local.conn


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for obtaining a database connection within a thread."""
    conn = get_db_connection()
    try:
        yield conn
    except Exception as e:
        logger.error(f"Database error: {str(e)}", exc_info=True)
        raise


@contextmanager
def db_transaction() -> Generator[sqlite3.Cursor, None, None]:
    """Context manager for atomic database transactions with an exclusive/immediate lock."""
    conn = get_db_connection()
    with _db_lock:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE;")
        try:
            yield cursor
            cursor.execute("COMMIT;")
        except Exception as e:
            cursor.execute("ROLLBACK;")
            logger.error(f"Transaction rolled back due to: {str(e)}")
            raise
        finally:
            cursor.close()


def init_db() -> None:
    """Initializes the database schema if tables do not exist."""
    db_path = get_db_path()
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = get_db_connection()

    schema = """
    -- Users / Principals
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT,
        created_at TEXT NOT NULL
    );

    -- Merchants
    CREATE TABLE IF NOT EXISTS merchants (
        merchant_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        is_verified INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    );

    -- Versioned Merchant Policies
    CREATE TABLE IF NOT EXISTS merchant_policies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        merchant_id TEXT NOT NULL,
        version TEXT NOT NULL,
        ai_sales_enabled INTEGER NOT NULL DEFAULT 1,
        max_ai_order_value_inr REAL NOT NULL,
        allowed_categories TEXT NOT NULL, -- JSON array
        allow_quantity_changes INTEGER NOT NULL DEFAULT 1,
        allow_substitutions INTEGER NOT NULL DEFAULT 0,
        allow_discounts INTEGER NOT NULL DEFAULT 1,
        max_discount_pct REAL NOT NULL DEFAULT 10.0,
        require_step_up_rules TEXT NOT NULL, -- JSON array
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        FOREIGN KEY (merchant_id) REFERENCES merchants (merchant_id),
        UNIQUE(merchant_id, version)
    );

    -- Machine-Readable Product Catalog
    CREATE TABLE IF NOT EXISTS products (
        sku TEXT PRIMARY KEY,
        merchant_id TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        category TEXT NOT NULL,
        price_inr REAL NOT NULL,
        currency TEXT NOT NULL DEFAULT 'INR',
        inventory INTEGER NOT NULL DEFAULT 0,
        delivery_estimate TEXT NOT NULL,
        installation_available INTEGER NOT NULL DEFAULT 0,
        substitution_allowed INTEGER NOT NULL DEFAULT 0,
        recurring_allowed INTEGER NOT NULL DEFAULT 0,
        ai_enabled INTEGER NOT NULL DEFAULT 1,
        specs_json TEXT, -- JSON attributes
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (merchant_id) REFERENCES merchants (merchant_id)
    );

    -- User Authorization Contracts
    CREATE TABLE IF NOT EXISTS authorization_contracts (
        contract_id TEXT PRIMARY KEY,
        principal_id TEXT NOT NULL,
        agent_id TEXT NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        merchants_allowlist TEXT NOT NULL, -- JSON array
        categories_allowlist TEXT NOT NULL, -- JSON array
        max_order_value_inr REAL NOT NULL,
        max_aggregate_value_inr REAL NOT NULL,
        budget_period TEXT NOT NULL DEFAULT 'weekly', -- 'per_order', 'daily', 'weekly', 'monthly', 'lifetime'
        recurring_allowed INTEGER NOT NULL DEFAULT 0,
        delivery_pincodes TEXT NOT NULL, -- JSON array
        approval_conditions TEXT NOT NULL, -- JSON array
        issued_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        is_revoked INTEGER NOT NULL DEFAULT 0,
        raw_natural_language TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (principal_id) REFERENCES users (user_id)
    );

    -- Atomic Budget Reservations
    CREATE TABLE IF NOT EXISTS budget_reservations (
        reservation_id TEXT PRIMARY KEY,
        contract_id TEXT NOT NULL,
        decision_id TEXT,
        transaction_id TEXT,
        amount_inr REAL NOT NULL,
        status TEXT NOT NULL, -- 'PENDING', 'COMMITTED', 'RELEASED', 'EXPIRED'
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        committed_at TEXT,
        released_at TEXT,
        FOREIGN KEY (contract_id) REFERENCES authorization_contracts (contract_id)
    );

    -- Authorization Decisions
    CREATE TABLE IF NOT EXISTS authorization_decisions (
        decision_id TEXT PRIMARY KEY,
        transaction_id TEXT NOT NULL,
        contract_id TEXT NOT NULL,
        contract_version INTEGER NOT NULL,
        merchant_id TEXT NOT NULL,
        merchant_policy_version TEXT NOT NULL,
        decision TEXT NOT NULL, -- 'ALLOW', 'CHALLENGE', 'DENY'
        matched_rules TEXT NOT NULL, -- JSON array
        failed_rules TEXT NOT NULL, -- JSON array
        challenge_reasons TEXT NOT NULL, -- JSON array
        canonical_transaction TEXT NOT NULL, -- JSON object
        agent_proposal TEXT, -- JSON object
        budget_state TEXT NOT NULL, -- JSON object
        reason_code TEXT NOT NULL,
        explanation TEXT,
        evaluated_at TEXT NOT NULL
    );

    -- Transactions
    CREATE TABLE IF NOT EXISTS transactions (
        transaction_id TEXT PRIMARY KEY,
        decision_id TEXT NOT NULL,
        contract_id TEXT NOT NULL,
        merchant_id TEXT NOT NULL,
        sku TEXT NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 1,
        total_inr REAL NOT NULL,
        currency TEXT NOT NULL DEFAULT 'INR',
        status TEXT NOT NULL, -- 'DRAFT', 'AUTHORIZED', 'RESERVED', 'PAYMENT_PENDING', 'COMPLETED', 'CHALLENGED', 'DENIED', 'FAILED'
        idempotency_key TEXT UNIQUE,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (decision_id) REFERENCES authorization_decisions (decision_id),
        FOREIGN KEY (contract_id) REFERENCES authorization_contracts (contract_id),
        FOREIGN KEY (merchant_id) REFERENCES merchants (merchant_id),
        FOREIGN KEY (sku) REFERENCES products (sku)
    );

    -- Payment Attempts
    CREATE TABLE IF NOT EXISTS payment_attempts (
        payment_id TEXT PRIMARY KEY,
        transaction_id TEXT NOT NULL,
        razorpay_order_id TEXT,
        razorpay_payment_id TEXT,
        amount_inr REAL NOT NULL,
        currency TEXT NOT NULL DEFAULT 'INR',
        status TEXT NOT NULL, -- 'INITIATED', 'SUCCESS', 'FAILED', 'VERIFIED'
        method TEXT NOT NULL DEFAULT 'razorpay_test_mode',
        signature TEXT,
        error_details TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (transaction_id) REFERENCES transactions (transaction_id)
    );

    -- Tamper-Evident Audit Event Chain
    CREATE TABLE IF NOT EXISTS audit_events (
        event_id TEXT PRIMARY KEY,
        sequence_num INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        decision_id TEXT,
        payload_json TEXT NOT NULL,
        prev_hash TEXT NOT NULL,
        current_hash TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        UNIQUE(sequence_num)
    );

    -- Step-Up Challenges
    CREATE TABLE IF NOT EXISTS step_up_challenges (
        challenge_id TEXT PRIMARY KEY,
        decision_id TEXT NOT NULL,
        transaction_id TEXT NOT NULL,
        status TEXT NOT NULL, -- 'PENDING', 'APPROVED', 'REJECTED', 'EXPIRED'
        reasons TEXT NOT NULL, -- JSON array
        created_at TEXT NOT NULL,
        resolved_at TEXT,
        resolved_by TEXT,
        FOREIGN KEY (decision_id) REFERENCES authorization_decisions (decision_id)
    );

    -- Indexes
    CREATE INDEX IF NOT EXISTS idx_products_merchant ON products(merchant_id);
    CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
    CREATE INDEX IF NOT EXISTS idx_policies_merchant ON merchant_policies(merchant_id, version);
    CREATE INDEX IF NOT EXISTS idx_contracts_principal ON authorization_contracts(principal_id);
    CREATE INDEX IF NOT EXISTS idx_reservations_contract ON budget_reservations(contract_id, status);
    CREATE INDEX IF NOT EXISTS idx_decisions_tx ON authorization_decisions(transaction_id);
    CREATE INDEX IF NOT EXISTS idx_audit_seq ON audit_events(sequence_num);
    """

    cursor = conn.cursor()
    cursor.executescript(schema)
    cursor.close()
    logger.info("Database schema initialized successfully.")
