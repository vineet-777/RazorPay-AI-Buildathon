"""FastAPI Main Application Entrypoint for Agent Commerce Gateway."""

import time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.db import init_db
from app.commerce.catalog import CatalogService
from app.commerce.merchant_policy import MerchantPolicyService
from app.authorization.contracts import ContractService
from app.api.routes import router as api_router
from app.core.logging import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes SQLite database and seeds realistic demo data on startup."""
    logger.info("Initializing Agent Commerce Gateway database schema and seed data...")
    init_db()
    CatalogService.seed_catalog()
    MerchantPolicyService.seed_policies()
    ContractService.seed_contracts()
    logger.info("Agent Commerce Gateway initialized successfully.")
    yield
    logger.info("Agent Commerce Gateway shutting down.")


app = FastAPI(
    title="Agent Commerce Gateway",
    description=(
        "Production-grade transaction infrastructure layer that turns Razorpay merchants "
        "into safe, machine-readable storefronts—letting AI buyers discover products, "
        "negotiate constraints, and complete payments under explicit user and merchant policies."
    ),
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_correlation_and_timing(request: Request, call_next):
    """Adds X-Request-ID and X-Response-Time-Ms correlation headers to all responses."""
    req_id = request.headers.get("X-Request-ID", f"req_{uuid.uuid4().hex[:8]}")
    start_time = time.perf_counter()

    response = await call_next(request)

    duration_ms = (time.perf_counter() - start_time) * 1000.0
    response.headers["X-Request-ID"] = req_id
    response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"
    return response


# Include API Router
app.include_router(api_router)


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": "1.0.0",
        "razorpay_mode": "TEST_MODE" if settings.RAZORPAY_TEST_MODE else "LIVE",
        "llm_provider": settings.LLM_PROVIDER
    }


# Mount Static UI Frontend (at root)
import os
from fastapi.staticfiles import StaticFiles
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
