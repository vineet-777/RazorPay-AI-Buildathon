"""Transaction and Payment Lifecycle State Machine."""

from typing import Set, Dict
from app.payments.models import TransactionStatus
from app.core.logging import logger


class InvalidStateTransitionError(Exception):
    """Raised when an illegal transaction state transition is attempted."""
    pass


class PaymentStateMachine:
    """Strict state machine governing autonomous commerce transaction states."""

    # Explicit allowed state transitions
    TRANSITIONS: Dict[TransactionStatus, Set[TransactionStatus]] = {
        TransactionStatus.DRAFT: {
            TransactionStatus.AUTHORIZATION_PENDING,
            TransactionStatus.DENIED,
            TransactionStatus.CHALLENGED
        },
        TransactionStatus.AUTHORIZATION_PENDING: {
            TransactionStatus.AUTHORIZED,
            TransactionStatus.CHALLENGED,
            TransactionStatus.DENIED,
            TransactionStatus.AUTHORIZATION_EXPIRED,
            TransactionStatus.AUTHORIZATION_REVOKED
        },
        TransactionStatus.AUTHORIZED: {
            TransactionStatus.RESERVED,
            TransactionStatus.PAYMENT_PENDING,
            TransactionStatus.RESERVATION_RELEASED,
            TransactionStatus.AUTHORIZATION_REVOKED
        },
        TransactionStatus.RESERVED: {
            TransactionStatus.PAYMENT_PENDING,
            TransactionStatus.RESERVATION_RELEASED
        },
        TransactionStatus.PAYMENT_PENDING: {
            TransactionStatus.COMPLETED,
            TransactionStatus.PAYMENT_FAILED,
            TransactionStatus.RESERVATION_RELEASED
        },
        TransactionStatus.CHALLENGED: {
            TransactionStatus.AUTHORIZED,
            TransactionStatus.DENIED,
            TransactionStatus.RESERVATION_RELEASED
        },
        # Terminal states
        TransactionStatus.COMPLETED: set(),
        TransactionStatus.DENIED: set(),
        TransactionStatus.PAYMENT_FAILED: {TransactionStatus.RESERVATION_RELEASED},
        TransactionStatus.AUTHORIZATION_EXPIRED: set(),
        TransactionStatus.AUTHORIZATION_REVOKED: {TransactionStatus.RESERVATION_RELEASED},
        TransactionStatus.RESERVATION_RELEASED: set()
    }

    @classmethod
    def validate_transition(cls, current_state: TransactionStatus, next_state: TransactionStatus) -> bool:
        allowed = cls.TRANSITIONS.get(current_state, set())
        if next_state not in allowed:
            err = f"Illegal state transition from {current_state.value} to {next_state.value}."
            logger.error(err)
            raise InvalidStateTransitionError(err)
        logger.info(f"Transaction transitioned: {current_state.value} -> {next_state.value}")
        return True
