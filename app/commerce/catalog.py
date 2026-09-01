from typing import Optional, List, Dict, Any
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.models import Product, Merchant
from app.schemas import ProductCreate, ProductUpdate, ProductSearchRequest, ProductSearchResponse, ProductResponse


class CatalogService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_product(self, merchant_id: str, product_data: ProductCreate) -> Product:
        product = Product(
            merchant_id=merchant_id,
            **product_data.model_dump()
        )
        self.session.add(product)
        await self.session.flush()
        await self.session.refresh(product)
        return product

    async def get_product(self, product_id: str) -> Optional[Product]:
        result = await self.session.execute(
            select(Product).where(Product.id == product_id)
        )
        return result.scalar_one_or_none()

    async def get_product_by_sku(self, merchant_id: str, sku: str) -> Optional[Product]:
        result = await self.session.execute(
            select(Product).where(
                and_(Product.merchant_id == merchant_id, Product.sku == sku)
            )
        )
        return result.scalar_one_or_none()

    async def update_product(self, product_id: str, product_data: ProductUpdate) -> Optional[Product]:
        product = await self.get_product(product_id)
        if not product:
            return None

        update_data = product_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(product, field, value)

        product.updated_at = datetime.utcnow()
        await self.session.flush()
        await self.session.refresh(product)
        return product

    async def delete_product(self, product_id: str) -> bool:
        product = await self.get_product(product_id)
        if not product:
            return False
        await self.session.delete(product)
        return True

    async def search_products(self, request: ProductSearchRequest) -> ProductSearchResponse:
        query = select(Product).where(Product.ai_commerce_eligible == True)

        if request.in_stock_only:
            query = query.where(Product.inventory > 0)

        if request.category:
            query = query.where(Product.category == request.category)

        if request.merchant_id:
            query = query.where(Product.merchant_id == request.merchant_id)

        if request.max_price_inr is not None:
            query = query.where(Product.price_inr <= request.max_price_inr)

        if request.min_price_inr is not None:
            query = query.where(Product.price_inr >= request.min_price_inr)

        if request.query:
            query = query.where(
                or_(
                    Product.title.ilike(f"%{request.query}%"),
                    Product.description.ilike(f"%{request.query}%"),
                    Product.sku.ilike(f"%{request.query}%"),
                )
            )

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar()

        query = query.order_by(Product.created_at.desc()).offset(request.offset).limit(request.limit)
        result = await self.session.execute(query)
        products = result.scalars().all()

        return ProductSearchResponse(
            products=[ProductResponse.model_validate(p) for p in products],
            total=total,
            limit=request.limit,
            offset=request.offset
        )

    async def get_merchant_products(self, merchant_id: str) -> List[Product]:
        result = await self.session.execute(
            select(Product).where(Product.merchant_id == merchant_id).order_by(Product.created_at.desc())
        )
        return result.scalars().all()

    async def get_categories(self) -> List[str]:
        result = await self.session.execute(
            select(Product.category).distinct().where(Product.ai_commerce_eligible == True)
        )
        return result.scalars().all()

    async def get_merchants_with_ai_commerce(self) -> List[Merchant]:
        result = await self.session.execute(
            select(Merchant).where(
                and_(Merchant.is_active == True, Merchant.ai_commerce_enabled == True)
            )
        )
        return result.scalars().all()