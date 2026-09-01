from typing import Optional, List
from sqlalchemy import select, and_, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import uuid

from app.models import (
    BudgetReservation, BudgetReservationStatus,
    UserAuthorization, UserAuthorizationStatus,
    Transaction, TransactionStatus
)
from app.config import get_settings


class BudgetService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()

    async def reserve_budget(
        self,
        authorization_id: str,
        amount_inr: int,
        transaction_id: str = None
    ) -> BudgetReservation:
        auth = await self.session.get(UserAuthorization, authorization_id)
        if not auth:
            raise ValueError("Authorization not found")

        if auth.status != UserAuthorizationStatus.ACTIVE:
            raise ValueError(f"Authorization is {auth.status.value}")

        if auth.expires_at < datetime.utcnow():
            auth.status = UserAuthorizationStatus.EXPIRED
            await self.session.flush()
            raise ValueError("Authorization has expired")

        if amount_inr > auth.max_order_value_inr:
            raise ValueError(f"Amount {amount_inr} exceeds max order value {auth.max_order_value_inr}")

        period_start = datetime.utcnow() - timedelta(days=auth.budget_period_days)

        result = await self.session.execute(
            select(func.coalesce(func.sum(BudgetReservation.amount_inr), 0))
            .where(
                and_(
                    BudgetReservation.authorization_id == authorization_id,
                    BudgetReservation.status.in_([
                        BudgetReservationStatus.RESERVED,
                        BudgetReservationStatus.COMMITTED
                    ]),
                    BudgetReservation.created_at >= period_start,
                )
            )
        )
        current_spent = result.scalar() or 0

        if current_spent + amount_inr > auth.max_aggregate_value_inr:
            raise ValueError(
                f"Aggregate budget exceeded: {current_spent} + {amount_inr} > {auth.max_aggregate_value_inr}"
            )

        expires_at = datetime.utcnow() + timedelta(seconds=self.settings.reservation_ttl_seconds)

        reservation = BudgetReservation(
            user_id=auth.user_id,
            authorization_id=authorization_id,
            transaction_id=transaction_id,
            amount_inr=amount_inr,
            status=BudgetReservationStatus.RESERVED,
            reserved_at=datetime.utcnow(),
            expires_at=expires_at,
        )
        self.session.add(reservation)
        await self.session.flush()
        await self.session.refresh(reservation)
        return reservation

    async def commit_reservation(self, reservation_id: str) -> Optional[BudgetReservation]:
        result = await self.session.execute(
            select(BudgetReservation).where(BudgetReservation.id == reservation_id)
        )
        reservation = result.scalar_one_or_none()

        if not reservation:
            return None

        if reservation.status != BudgetReservationStatus.RESERVED:
            raise ValueError(f"Reservation is {reservation.status.value}, cannot commit")

        reservation.status = BudgetReservationStatus.COMMITTED
        reservation.committed_at = datetime.utcnow()
        await self.session.flush()
        await self.session.refresh(reservation)
        return reservation

    async def release_reservation(self, reservation_id: str) -> Optional[BudgetReservation]:
        result = await self.session.execute(
            select(BudgetReservation).where(BudgetReservation.id == reservation_id)
        )
        reservation = result.scalar_one_or_none()

        if not reservation:
            return None

        if reservation.status in [BudgetReservationStatus.COMMITTED, BudgetReservationStatus.RELEASED]:
            return reservation

        reservation.status = BudgetReservationStatus.RELEASED
        reservation.released_at = datetime.utcnow()
        await self.session.flush()
        await self.session.refresh(reservation)
        return reservation

    async def get_reservation(self, reservation_id: str) -> Optional[BudgetReservation]:
        result = await self.session.execute(
            select(BudgetReservation).where(BudgetReservation.id == reservation_id)
        )
        return result.scalar_one_or_none()

    async def get_reservation_by_transaction(self, transaction_id: str) -> Optional[BudgetReservation]:
        result = await self.session.execute(
            select(BudgetReservation).where(BudgetReservation.transaction_id == transaction_id)
        )
        return result.scalar_one_or_none()

    async def expire_reservations(self) -> int:
        result = await self.session.execute(
            update(BudgetReservation)
            .where(
                and_(
                    BudgetReservation.status == BudgetReservationStatus.RESERVED,
                    BudgetReservation.expires_at < datetime.utcnow(),
                )
            )
            .values(status=BudgetReservationStatus.EXPIRED, released_at=datetime.utcnow())
        )
        return result.rowcount

    async def get_active_reservations(self, authorization_id: str) -> List[BudgetReservation]:
        result = await self.session.execute(
            select(BudgetReservation)
            .where(
                and_(
                    BudgetReservation.authorization_id == authorization_id,
                    BudgetReservation.status.in_([
                        BudgetReservationStatus.RESERVED,
                        BudgetReservationStatus.COMMITTED
                    ])
                )
            )
        )
        return result.scalars().all()

    async def get_available_budget(self, authorization_id: str) -> int:
        auth = await self.session.get(UserAuthorization, authorization_id)
        if not auth:
            return 0

        period_start = datetime.utcnow() - timedelta(days=auth.budget_period_days)

        result = await self.session.execute(
            select(func.coalesce(func.sum(BudgetReservation.amount_inr), 0))
            .where(
                and_(
                    BudgetReservation.authorization_id == authorization_id,
                    BudgetReservation.status.in_([
                        BudgetReservationStatus.RESERVED,
                        BudgetReservationStatus.COMMITTED
                    ]),
                    BudgetReservation.created_at >= period_start,
                )
            )
        )
        current_spent = result.scalar() or 0

        return max(0, auth.max_aggregate_value_inr - current_spent)