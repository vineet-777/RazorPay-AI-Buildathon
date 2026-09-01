from typing import Optional, List
from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import uuid

from app.models import UserAuthorization, User, Agent, UserAuthorizationStatus
from app.schemas import UserAuthorizationCreate, UserAuthorizationResponse, UserAuthorizationStatus as SchemaAuthStatus


class AuthorizationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_authorization(
        self,
        user_id: str,
        auth_data: UserAuthorizationCreate
    ) -> UserAuthorization:
        user = await self.session.get(User, user_id)
        if not user:
            raise ValueError("User not found")

        agent = await self.session.get(Agent, auth_data.agent_id)
        if not agent:
            raise ValueError("Agent not found")

        contract_id = f"auth_{uuid.uuid4().hex[:12]}"
        expires_at = datetime.utcnow() + timedelta(days=auth_data.expires_in_days)

        authorization = UserAuthorization(
            user_id=user_id,
            agent_id=auth_data.agent_id,
            contract_id=contract_id,
            version=1,
            merchants_allowlist=auth_data.merchants_allowlist,
            categories_allowlist=auth_data.categories_allowlist,
            max_order_value_inr=auth_data.max_order_value_inr,
            max_aggregate_value_inr=auth_data.max_aggregate_value_inr,
            budget_period_days=auth_data.budget_period_days,
            recurring_purchase_allowed=auth_data.recurring_purchase_allowed,
            delivery_pincodes=auth_data.delivery_pincodes,
            approval_conditions=auth_data.approval_conditions,
            expires_at=expires_at,
            status=UserAuthorizationStatus.ACTIVE,
        )
        self.session.add(authorization)
        await self.session.flush()
        await self.session.refresh(authorization)
        return authorization

    async def get_authorization(self, auth_id: str) -> Optional[UserAuthorization]:
        result = await self.session.execute(
            select(UserAuthorization).where(UserAuthorization.id == auth_id)
        )
        return result.scalar_one_or_none()

    async def get_authorization_by_contract(self, contract_id: str) -> Optional[UserAuthorization]:
        result = await self.session.execute(
            select(UserAuthorization).where(UserAuthorization.contract_id == contract_id)
        )
        return result.scalar_one_or_none()

    async def get_active_authorization(self, user_id: str, agent_id: str) -> Optional[UserAuthorization]:
        result = await self.session.execute(
            select(UserAuthorization)
            .where(
                and_(
                    UserAuthorization.user_id == user_id,
                    UserAuthorization.agent_id == agent_id,
                    UserAuthorization.status == UserAuthorizationStatus.ACTIVE,
                    UserAuthorization.expires_at > datetime.utcnow(),
                )
            )
            .order_by(desc(UserAuthorization.version))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_user_authorizations(self, user_id: str) -> List[UserAuthorization]:
        result = await self.session.execute(
            select(UserAuthorization)
            .where(UserAuthorization.user_id == user_id)
            .order_by(desc(UserAuthorization.created_at))
        )
        return result.scalars().all()

    async def revoke_authorization(self, auth_id: str, revocation_version: int = None) -> Optional[UserAuthorization]:
        auth = await self.get_authorization(auth_id)
        if not auth:
            return None

        auth.status = UserAuthorizationStatus.REVOKED
        auth.revoked_at = datetime.utcnow()
        auth.revocation_version = (revocation_version or auth.revocation_version) + 1
        await self.session.flush()
        await self.session.refresh(auth)
        return auth

    async def check_authorization_valid(self, auth: UserAuthorization) -> tuple[bool, Optional[str]]:
        if auth.status != UserAuthorizationStatus.ACTIVE:
            return False, f"Authorization status is {auth.status.value}"

        if auth.expires_at < datetime.utcnow():
            auth.status = UserAuthorizationStatus.EXPIRED
            await self.session.flush()
            return False, "Authorization has expired"

        return True, None

    async def get_aggregate_spent(
        self,
        user_id: str,
        agent_id: str,
        period_days: int
    ) -> int:
        since = datetime.utcnow() - timedelta(days=period_days)

        result = await self.session.execute(
            select(func.coalesce(func.sum(BudgetReservation.amount_inr), 0))
            .join(UserAuthorization, BudgetReservation.authorization_id == UserAuthorization.id)
            .where(
                and_(
                    UserAuthorization.user_id == user_id,
                    UserAuthorization.agent_id == agent_id,
                    BudgetReservation.status.in_([
                        BudgetReservationStatus.RESERVED,
                        BudgetReservationStatus.COMMITTED
                    ]),
                    BudgetReservation.created_at >= since,
                )
            )
        )
        from app.models import BudgetReservation, BudgetReservationStatus
        return result.scalar() or 0

    async def get_authorization_response(self, auth: UserAuthorization) -> UserAuthorizationResponse:
        return UserAuthorizationResponse.model_validate(auth)