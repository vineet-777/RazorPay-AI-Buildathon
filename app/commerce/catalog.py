"""Machine-readable Merchant Catalog Service."""

import json
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from app.core.db import get_db, db_transaction
from app.commerce.models import Product, Merchant
from app.core.logging import logger

# Rich realistic seed data for merchants and machine-readable products
SEED_MERCHANTS: List[Dict[str, Any]] = [
    {"merchant_id": "merchant_freshmart", "name": "FreshMart Supermarket", "category": "groceries"},
    {"merchant_id": "merchant_croma_store", "name": "Croma Digital Electronics", "category": "electronics"},
    {"merchant_id": "merchant_apothecary", "name": "Apollo Wellness & Personal Care", "category": "personal_care"},
    {"merchant_id": "merchant_quickdash", "name": "QuickDash Local Convenience", "category": "groceries"},
    {"merchant_id": "merchant_untrusted", "name": "Shady Bargains Unverified", "category": "electronics", "is_verified": False},
]

SEED_PRODUCTS: List[Dict[str, Any]] = [
    # Groceries
    {
        "sku": "GROC-ORGANIC-OATS-1KG",
        "merchant_id": "merchant_freshmart",
        "title": "Organic Rolled Oats 1kg",
        "description": "100% whole grain organic gluten-free rolled oats",
        "category": "groceries",
        "price_inr": 349.0,
        "inventory": 85,
        "delivery_estimate": "1 day",
        "installation_available": False,
        "substitution_allowed": True,
        "recurring_allowed": True,
        "ai_enabled": True,
        "specs": {"weight": "1kg", "organic": True, "brand": "TrueElements"}
    },
    {
        "sku": "GROC-ALMOND-MILK-1L",
        "merchant_id": "merchant_freshmart",
        "title": "Unsweetened Almond Milk 1L Pack of 3",
        "description": "Plant-based lactose-free fortified almond beverage",
        "category": "groceries",
        "price_inr": 720.0,
        "inventory": 40,
        "delivery_estimate": "1 day",
        "installation_available": False,
        "substitution_allowed": False,
        "recurring_allowed": True,
        "ai_enabled": True,
        "specs": {"volume": "3L", "dietary": "vegan", "brand": "RawPressery"}
    },
    {
        "sku": "GROC-OLIVE-OIL-1L",
        "merchant_id": "merchant_freshmart",
        "title": "Extra Virgin Cold Pressed Olive Oil 1L",
        "description": "Imported Mediterranean cold-pressed extra virgin olive oil",
        "category": "groceries",
        "price_inr": 1249.0,
        "inventory": 25,
        "delivery_estimate": "1-2 days",
        "installation_available": False,
        "substitution_allowed": False,
        "recurring_allowed": False,
        "ai_enabled": True,
        "specs": {"volume": "1L", "origin": "Spain", "brand": "Borges"}
    },
    {
        "sku": "GROC-PREMIUM-BASKET",
        "merchant_id": "merchant_freshmart",
        "title": "Weekly Organic Pantry Essentials Basket",
        "description": "Assorted fresh produce, sourdough bread, organic butter, and pantry goods",
        "category": "groceries",
        "price_inr": 2499.0,
        "inventory": 18,
        "delivery_estimate": "Same day",
        "installation_available": False,
        "substitution_allowed": True,
        "recurring_allowed": True,
        "ai_enabled": True,
        "specs": {"items_count": 12, "shelf_life": "7 days"}
    },

    # Electronics (Core Demo Scenarios)
    {
        "sku": "SONY-65X80L-4K",
        "merchant_id": "merchant_croma_store",
        "title": "Sony Bravia 65-inch 4K Ultra HD Smart LED Google TV (KD-65X80L)",
        "description": "4K HDR processor X1, Dolby Vision/Atmos, Google TV interface with voice control",
        "category": "electronics",
        "price_inr": 68999.0,
        "inventory": 12,
        "delivery_estimate": "2-4 days",
        "installation_available": True,
        "substitution_allowed": False,
        "recurring_allowed": False,
        "ai_enabled": True,
        "specs": {"screen_size": "65 inch", "resolution": "4K", "brand": "Sony", "free_installation": True}
    },
    {
        "sku": "LG-65UR7500-4K",
        "merchant_id": "merchant_croma_store",
        "title": "LG 65-inch 4K Ultra HD Smart LED TV (65UR7500PSC)",
        "description": "Alpha 5 AI processor 4K Gen6, webOS 23 with ThinQ AI",
        "category": "electronics",
        "price_inr": 62990.0,
        "inventory": 9,
        "delivery_estimate": "2-3 days",
        "installation_available": True,
        "substitution_allowed": False,
        "recurring_allowed": False,
        "ai_enabled": True,
        "specs": {"screen_size": "65 inch", "resolution": "4K", "brand": "LG", "free_installation": True}
    },
    {
        "sku": "SONY-75X90L-4K",
        "merchant_id": "merchant_croma_store",
        "title": "Sony Bravia 75-inch XR Full Array LED 4K TV (XR-75X90L)",
        "description": "Cognitive Processor XR, Full Array LED contrast, XR Triluminos Pro",
        "category": "electronics",
        "price_inr": 184990.0,
        "inventory": 4,
        "delivery_estimate": "3-5 days",
        "installation_available": True,
        "substitution_allowed": False,
        "recurring_allowed": False,
        "ai_enabled": True,
        "specs": {"screen_size": "75 inch", "resolution": "4K", "brand": "Sony"}
    },
    {
        "sku": "SONY-WH1000XM5-BLK",
        "merchant_id": "merchant_croma_store",
        "title": "Sony WH-1000XM5 Wireless Industry Leading Noise Canceling Headphones",
        "description": "Two processors, 8 microphones, Auto NC Optimizer, 30hr battery life",
        "category": "electronics",
        "price_inr": 26990.0,
        "inventory": 30,
        "delivery_estimate": "1-2 days",
        "installation_available": False,
        "substitution_allowed": False,
        "recurring_allowed": False,
        "ai_enabled": True,
        "specs": {"type": "over-ear", "anc": True, "battery": "30 hours"}
    },

    # Personal Care
    {
        "sku": "PC-CERAVE-CLEANSER-473ML",
        "merchant_id": "merchant_apothecary",
        "title": "CeraVe Hydrating Facial Cleanser 473ml",
        "description": "Non-foaming lotion cleanser with essential ceramides and hyaluronic acid",
        "category": "personal_care",
        "price_inr": 1150.0,
        "inventory": 50,
        "delivery_estimate": "2 days",
        "installation_available": False,
        "substitution_allowed": False,
        "recurring_allowed": True,
        "ai_enabled": True,
        "specs": {"skin_type": "Normal to Dry", "dermatologist_tested": True}
    },
    {
        "sku": "PC-MINIMALIST-SUNSCREEN-50G",
        "merchant_id": "merchant_apothecary",
        "title": "Minimalist Sunscreen SPF 50 PA++++ Multi-Vitamin",
        "description": "Broad spectrum lightweight sunscreen lotion with Niacinamide & Vitamin B5",
        "category": "personal_care",
        "price_inr": 399.0,
        "inventory": 100,
        "delivery_estimate": "1-2 days",
        "installation_available": False,
        "substitution_allowed": True,
        "recurring_allowed": True,
        "ai_enabled": True,
        "specs": {"spf": 50, "pa_rating": "PA++++"}
    },

    # Quick convenience items
    {
        "sku": "QUICK-ARTISAN-COFFEE-250G",
        "merchant_id": "merchant_quickdash",
        "title": "Blue Tokai Attikan Estate Arabica Coffee 250g",
        "description": "Dark roast whole bean specialty single-estate coffee",
        "category": "groceries",
        "price_inr": 480.0,
        "inventory": 20,
        "delivery_estimate": "30 mins",
        "installation_available": False,
        "substitution_allowed": False,
        "recurring_allowed": True,
        "ai_enabled": True,
        "specs": {"roast": "Dark", "origin": "Biligirirangan Hills"}
    },

    # Adversarial / Edge Case items
    {
        "sku": "SHADY-MUTATED-GADGET-999",
        "merchant_id": "merchant_untrusted",
        "title": "Counterfeit Smart Watch Ultra Pro",
        "description": "Unverified grey-market electronic gadget",
        "category": "electronics",
        "price_inr": 4999.0,
        "inventory": 5,
        "delivery_estimate": "7 days",
        "installation_available": False,
        "substitution_allowed": False,
        "recurring_allowed": False,
        "ai_enabled": False,  # AI Disabled by merchant!
        "specs": {"verified": False}
    },
    {
        "sku": "GROC-OUT-OF-STOCK-CAVIAR",
        "merchant_id": "merchant_freshmart",
        "title": "Beluga Sturgeon Caviar 50g Tin",
        "description": "Ultra luxury gourmet wild sturgeon caviar",
        "category": "groceries",
        "price_inr": 9500.0,
        "inventory": 0,  # Zero Inventory
        "delivery_estimate": "Out of stock",
        "installation_available": False,
        "substitution_allowed": False,
        "recurring_allowed": False,
        "ai_enabled": True,
        "specs": {"inventory_status": "DEPLETED"}
    }
]


class CatalogService:
    @staticmethod
    def seed_catalog() -> None:
        """Seeds initial merchants and products into the database if empty."""
        with db_transaction() as cursor:
            now = datetime.now(timezone.utc).isoformat()

            # Seed Merchants
            for m in SEED_MERCHANTS:
                cursor.execute(
                    """
                    INSERT INTO merchants (merchant_id, name, category, is_verified, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(merchant_id) DO UPDATE SET
                        name=excluded.name,
                        category=excluded.category,
                        is_verified=excluded.is_verified
                    """,
                    (m["merchant_id"], m["name"], m["category"], 1 if m.get("is_verified", True) else 0, now)
                )

            # Seed Products
            for p in SEED_PRODUCTS:
                cursor.execute(
                    """
                    INSERT INTO products (
                        sku, merchant_id, title, description, category, price_inr,
                        currency, inventory, delivery_estimate, installation_available,
                        substitution_allowed, recurring_allowed, ai_enabled, specs_json,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(sku) DO UPDATE SET
                        price_inr=excluded.price_inr,
                        inventory=excluded.inventory,
                        delivery_estimate=excluded.delivery_estimate,
                        installation_available=excluded.installation_available,
                        substitution_allowed=excluded.substitution_allowed,
                        recurring_allowed=excluded.recurring_allowed,
                        ai_enabled=excluded.ai_enabled,
                        specs_json=excluded.specs_json,
                        updated_at=excluded.updated_at
                    """,
                    (
                        p["sku"], p["merchant_id"], p["title"], p["description"], p["category"],
                        p["price_inr"], p.get("currency", "INR"), p["inventory"], p["delivery_estimate"],
                        1 if p["installation_available"] else 0,
                        1 if p["substitution_allowed"] else 0,
                        1 if p["recurring_allowed"] else 0,
                        1 if p["ai_enabled"] else 0,
                        json.dumps(p.get("specs", {})),
                        now, now
                    )
                )
        logger.info("Machine-readable merchant catalog seeded successfully.")

    @staticmethod
    def get_product(sku: str) -> Optional[Product]:
        """Retrieves a product by SKU."""
        with get_db() as conn:
            row = conn.execute("SELECT * FROM products WHERE sku = ?", (sku,)).fetchone()
            if not row:
                return None
            return CatalogService._row_to_product(row)

    @staticmethod
    def list_products(
        category: Optional[str] = None,
        merchant_id: Optional[str] = None,
        max_price: Optional[float] = None,
        query: Optional[str] = None,
        ai_enabled_only: bool = True
    ) -> List[Product]:
        """Search products with filters for AI discovery."""
        sql = "SELECT * FROM products WHERE 1=1"
        params: List[Any] = []

        if ai_enabled_only:
            sql += " AND ai_enabled = 1"
        if category:
            sql += " AND category = ?"
            params.append(category)
        if merchant_id:
            sql += " AND merchant_id = ?"
            params.append(merchant_id)
        if max_price is not None:
            sql += " AND price_inr <= ?"
            params.append(max_price)
        if query:
            sql += " AND (title LIKE ? OR description LIKE ?)"
            pattern = f"%{query}%"
            params.extend([pattern, pattern])

        sql += " ORDER BY price_inr ASC"

        with get_db() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [CatalogService._row_to_product(r) for r in rows]

    @staticmethod
    def _row_to_product(row: Any) -> Product:
        specs = {}
        if row["specs_json"]:
            try:
                specs = json.loads(row["specs_json"])
            except Exception:
                specs = {}

        return Product(
            sku=row["sku"],
            merchant_id=row["merchant_id"],
            title=row["title"],
            description=row["description"],
            category=row["category"],
            price_inr=float(row["price_inr"]),
            currency=row["currency"],
            inventory=int(row["inventory"]),
            delivery_estimate=row["delivery_estimate"],
            installation_available=bool(row["installation_available"]),
            substitution_allowed=bool(row["substitution_allowed"]),
            recurring_allowed=bool(row["recurring_allowed"]),
            ai_enabled=bool(row["ai_enabled"]),
            specs=specs
        )
