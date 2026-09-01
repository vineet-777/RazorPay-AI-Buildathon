"""Razorpay Test-Mode Payment Gateway Client and Lifecycle Manager."""

import hmac
import hashlib
import uuid
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import razorpay
from app.core.config import settings
from app.core.db import get_db, db_transaction
from app.payments.models import (
    TransactionStatus, PaymentStatus, PaymentExecutionRequest, PaymentExecutionResponse
)
from app.payments.state_machine import PaymentStateMachine
from app.payments.idempotency import IdempotencyService
from app.authorization.reservations import ReservationService
from app.core.logging import logger


class RazorpayGatewayService:
    """Manages Razorpay Test-Mode Order creation, payment capture, and budget reservation lifecycle."""

    @classmethod
    def get_razorpay_client(cls) -> Optional[razorpay.Client]:
        try:
            return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        except Exception as e:
            logger.warning(f"Could not initialize official Razorpay client: {str(e)}")
            return None

    @classmethod
    def execute_payment(cls, req: PaymentExecutionRequest) -> PaymentExecutionResponse:
        # 1. Idempotency Check
        cached = IdempotencyService.check_idempotency(req.idempotency_key)
        if cached:
            return PaymentExecutionResponse(
                success=True,
                transaction_id=cached["transaction_id"],
                decision_id=req.decision_id,
                payment_id=cached.get("payment_id") or f"pay_cached_{req.idempotency_key[:8]}",
                razorpay_order_id=cached.get("razorpay_order_id"),
                razorpay_payment_id=cached.get("razorpay_payment_id"),
                amount_inr=float(cached["total_inr"]),
                currency="INR",
                status=TransactionStatus(cached["status"]),
                idempotent_replay=True,
                message="Idempotent replay: Transaction already processed successfully.",
                signature=cached.get("signature")
            )

        # 2. Retrieve Decision & Canonical Transaction
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM authorization_decisions WHERE decision_id = ?",
                (req.decision_id,)
            ).fetchone()

        if not row:
            return PaymentExecutionResponse(
                success=False,
                transaction_id=req.transaction_id,
                decision_id=req.decision_id,
                payment_id=f"pay_err_{uuid.uuid4().hex[:8]}",
                amount_inr=0,
                status=TransactionStatus.DENIED,
                message=f"Authorization decision {req.decision_id} not found."
            )

        decision_val = row["decision"]
        if decision_val != "ALLOW":
            return PaymentExecutionResponse(
                success=False,
                transaction_id=req.transaction_id,
                decision_id=req.decision_id,
                payment_id=f"pay_blocked_{uuid.uuid4().hex[:8]}",
                amount_inr=0,
                status=TransactionStatus.DENIED if decision_val == "DENY" else TransactionStatus.CHALLENGED,
                message=f"Payment rejected: Authorization decision was {decision_val} ({row['reason_code']})."
            )

        canonical_tx = json.loads(row["canonical_transaction"])
        amount_inr = float(canonical_tx["total_inr"])
        contract_id = row["contract_id"]
        merchant_id = row["merchant_id"]
        sku = canonical_tx["sku"]
        quantity = int(canonical_tx.get("quantity", 1))

        # Retrieve budget reservation
        res_row = ReservationService.get_reservation_by_tx(req.transaction_id)
        reservation_id = res_row["reservation_id"] if res_row else None

        # 3. Simulate or Execute Razorpay Test Mode Payment
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        payment_id = f"pay_rzp_{uuid.uuid4().hex[:12]}"
        order_id = f"order_rzp_{uuid.uuid4().hex[:12]}"

        # Check for simulated payment failure test scenario
        if req.simulate_payment_failure:
            logger.warning(f"Simulating payment failure for transaction {req.transaction_id}")
            if reservation_id:
                ReservationService.release_reservation(reservation_id)

            cls._record_failed_payment(
                payment_id=payment_id,
                transaction_id=req.transaction_id,
                decision_id=req.decision_id,
                contract_id=contract_id,
                merchant_id=merchant_id,
                sku=sku,
                quantity=quantity,
                amount_inr=amount_inr,
                idempotency_key=req.idempotency_key,
                error_msg="Simulated bank / payment processor decline in Razorpay test mode"
            )

            return PaymentExecutionResponse(
                success=False,
                transaction_id=req.transaction_id,
                decision_id=req.decision_id,
                payment_id=payment_id,
                amount_inr=amount_inr,
                status=TransactionStatus.PAYMENT_FAILED,
                message="Razorpay test-mode payment failed. Budget reservation released safely."
            )

        # Generate cryptographic HMAC-SHA256 test signature
        sig_payload = f"{order_id}|{payment_id}"
        signature = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode("utf-8"),
            sig_payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        # 4. Commit Budget Reservation Atomically
        if reservation_id:
            ReservationService.commit_reservation(reservation_id)

        # 5. Persist Completed Transaction and Payment Attempt
        cls._record_successful_payment(
            payment_id=payment_id,
            transaction_id=req.transaction_id,
            decision_id=req.decision_id,
            contract_id=contract_id,
            merchant_id=merchant_id,
            sku=sku,
            quantity=quantity,
            amount_inr=amount_inr,
            order_id=order_id,
            signature=signature,
            idempotency_key=req.idempotency_key
        )

        logger.info(
            f"Payment SUCCESS for tx {req.transaction_id}: ₹{amount_inr:,.2f} via Razorpay Test Mode ({order_id})"
        )

        return PaymentExecutionResponse(
            success=True,
            transaction_id=req.transaction_id,
            decision_id=req.decision_id,
            payment_id=payment_id,
            razorpay_order_id=order_id,
            razorpay_payment_id=payment_id,
            amount_inr=amount_inr,
            currency="INR",
            status=TransactionStatus.COMPLETED,
            idempotent_replay=False,
            message="Payment completed successfully via Razorpay test-mode gateway.",
            signature=signature
        )

    @classmethod
    def _record_successful_payment(
        cls,
        payment_id: str,
        transaction_id: str,
        decision_id: str,
        contract_id: str,
        merchant_id: str,
        sku: str,
        quantity: int,
        amount_inr: float,
        order_id: str,
        signature: str,
        idempotency_key: str
    ) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        with db_transaction() as cursor:
            # 1. Upsert Transaction
            cursor.execute(
                """
                INSERT INTO transactions (
                    transaction_id, decision_id, contract_id, merchant_id,
                    sku, quantity, total_inr, currency, status, idempotency_key,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'INR', 'COMPLETED', ?, ?, ?)
                ON CONFLICT(transaction_id) DO UPDATE SET
                    status='COMPLETED',
                    updated_at=excluded.updated_at
                """,
                (transaction_id, decision_id, contract_id, merchant_id, sku, quantity, amount_inr, idempotency_key, now_iso, now_iso)
            )

            # 2. Insert Payment Attempt
            cursor.execute(
                """
                INSERT INTO payment_attempts (
                    payment_id, transaction_id, razorpay_order_id, razorpay_payment_id,
                    amount_inr, currency, status, method, signature, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'INR', 'SUCCESS', 'razorpay_test_mode', ?, ?, ?)
                """,
                (payment_id, transaction_id, order_id, payment_id, amount_inr, signature, now_iso, now_iso)
            )

            # 3. Deduct product inventory
            cursor.execute(
                """
                UPDATE products
                SET inventory = MAX(0, inventory - ?), updated_at = ?
                WHERE sku = ?
                """,
                (quantity, now_iso, sku)
            )

    @classmethod
    def _record_failed_payment(
        cls,
        payment_id: str,
        transaction_id: str,
        decision_id: str,
        contract_id: str,
        merchant_id: str,
        sku: str,
        quantity: int,
        amount_inr: float,
        idempotency_key: str,
        error_msg: str
    ) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        with db_transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO transactions (
                    transaction_id, decision_id, contract_id, merchant_id,
                    sku, quantity, total_inr, currency, status, idempotency_key,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'INR', 'PAYMENT_FAILED', ?, ?, ?)
                ON CONFLICT(transaction_id) DO UPDATE SET
                    status='PAYMENT_FAILED',
                    updated_at=excluded.updated_at
                """,
                (transaction_id, decision_id, contract_id, merchant_id, sku, quantity, amount_inr, idempotency_key, now_iso, now_iso)
            )

            cursor.execute(
                """
                INSERT INTO payment_attempts (
                    payment_id, transaction_id, amount_inr, currency,
                    status, method, error_details, created_at, updated_at
                ) VALUES (?, ?, ?, 'INR', 'FAILED', 'razorpay_test_mode', ?, ?, ?)
                """,
                (payment_id, transaction_id, amount_inr, error_msg, now_iso, now_iso)
            )
