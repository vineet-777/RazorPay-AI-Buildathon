from typing import Optional, List
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.models import MerchantPolicy, Merchant
from app.schemas import MerchantPolicyCreate, MerchantPolicyResponse, MerchantPolicyStatus


class MerchantPolicyService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_policy(self, merchant_id: str, policy_data: MerchantPolicyCreate) -> MerchantPolicy:
        latest_version = await self.get_latest_version(merchant_id)
        new_version = (latest_version + 1) if latest_version else 1

        policy = MerchantPolicy(
            merchant_id=merchant_id,
            version=new_version,
            **policy_data.model_dump(),
            status=MerchantPolicyStatus.ACTIVE,
            activated_at=datetime.utcnow(),
        )
        self.session.add(policy)

        if latest_version:
            await self.archive_latest(merchant_id)

        await self.session.flush()
        await self.session.refresh(policy)
        return policy

    async def get_latest_version(self, merchant_id: str) -> Optional[int]:
        result = await self.session.execute(
            select(MerchantPolicy.version)
            .where(MerchantPolicy.merchant_id == merchant_id)
            .order_by(desc(MerchantPolicy.version))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_active_policy(self, merchant_id: str) -> Optional[MerchantPolicy]:
        result = await self.session.execute(
            select(MerchantPolicy)
            .where(
                and_(
                    MerchantPolicy.merchant_id == merchant_id,
                    MerchantPolicy.status == MerchantPolicyStatus.ACTIVE
                )
            )
            .order_by(desc(MerchantPolicy.version))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_policy_by_version(self, merchant_id: str, version: int) -> Optional[MerchantPolicy]:
        result = await self.session.execute(
            select(MerchantPolicy).where(
                and_(
                    MerchantPolicy.merchant_id == merchant_id,
                    MerchantPolicy.version == version
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_all_policies(self, merchant_id: str) -> List[MerchantPolicy]:
        result = await self.session.execute(
            select(MerchantPolicy)
            .where(MerchantPolicy.merchant_id == merchant_id)
            .order_by(desc(MerchantPolicy.version))
        )
        return result.scalars().all()

    async def archive_latest(self, merchant_id: str) -> bool:
        policy = await self.get_active_policy(merchant_id)
        if policy:
            policy.status = MerchantPolicyStatus.ARCHIVED
            policy.archived_at = datetime.utcnow()
            await self.session.flush()
            return True
        return False

    async def update_policy(self, merchant_id: str, policy_data: MerchantPolicyCreate) -> MerchantPolicy:
        return await self.create_policy(merchant_id, policy_data)

    async def get_policy_response(self, policy: MerchantPolicy) -> MerchantPolicyResponse:
        return MerchantPolicyResponse.model_validate(policy)