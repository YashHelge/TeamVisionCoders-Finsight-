"""
FinSight — Production-grade personal finance intelligence API.

FastAPI application with lifespan events for database pool, Redis,
and Bloom Filter initialization.
"""

import logging
from contextlib import asynccontextmanager

import asyncpg
import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings

# ── Globals ──
db_pool: asyncpg.Pool | None = None
redis_client: aioredis.Redis | None = None

logger = logging.getLogger("finsight")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB pool, Redis, rebuild Bloom Filters. Shutdown: cleanup."""
    global db_pool, redis_client

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )
    logger.info("FinSight starting up — environment=%s", settings.ENVIRONMENT)

    # ── Database connection pool ──
    try:
        db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        db_pool = await asyncpg.create_pool(db_url, min_size=2, max_size=10)
        logger.info("Database pool created")
    except Exception as e:
        logger.warning("Database pool creation failed: %s — running without DB", e)
        db_pool = None

    # ── Redis ──
    try:
        redis_client = aioredis.from_url(
            settings.REDIS_URL, decode_responses=True, max_connections=20
        )
        await redis_client.ping()
        logger.info("Redis connected")
    except Exception as e:
        logger.warning("Redis connection failed: %s — running without Redis", e)
        redis_client = None

    # ── Bloom Filter rebuild ──
    if db_pool and redis_client:
        try:
            from sync.dedup_gate import rebuild_bloom_filters
            await rebuild_bloom_filters(db_pool, redis_client)
            logger.info("Bloom Filters rebuilt from database")
        except Exception as e:
            logger.warning("Bloom Filter rebuild skipped: %s", e)

    # ── Store refs on app state ──
    app.state.db_pool = db_pool
    app.state.redis = redis_client

    yield

    # ── Shutdown ──
    if db_pool:
        await db_pool.close()
        logger.info("Database pool closed")
    if redis_client:
        await redis_client.close()
        logger.info("Redis connection closed")
    logger.info("FinSight shut down")


# ── FastAPI App ──
app = FastAPI(
    title="FinSight API",
    description="Production-grade personal finance intelligence system for the Indian digital transaction ecosystem.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──
from api.auth import router as auth_router
from api.sync import router as sync_router
from api.dedup import router as dedup_router
from api.checkpoint import router as checkpoint_router
from api.transactions import router as transactions_router
from api.analytics import router as analytics_router
from api.subscriptions import router as subscriptions_router
from api.ai_chat import router as ai_chat_router
from api.dataset import router as dataset_router
from api.model_update import router as model_update_router
from api.sms_ingest import router as sms_ingest_router

app.include_router(auth_router, prefix="/api/v1", tags=["Auth"])
app.include_router(sync_router, prefix="/api/v1", tags=["Sync"])
app.include_router(dedup_router, prefix="/api/v1", tags=["Dedup"])
app.include_router(checkpoint_router, prefix="/api/v1", tags=["Checkpoint"])
app.include_router(transactions_router, prefix="/api/v1", tags=["Transactions"])
app.include_router(analytics_router, prefix="/api/v1", tags=["Analytics"])
app.include_router(subscriptions_router, prefix="/api/v1", tags=["Subscriptions"])
app.include_router(ai_chat_router, prefix="/api/v1", tags=["AI Chat"])
app.include_router(dataset_router, prefix="/api/v1", tags=["Dataset"])
app.include_router(model_update_router, prefix="/api/v1", tags=["Model Update"])
app.include_router(sms_ingest_router, prefix="/api/v1", tags=["SMS Ingest"])


@app.get("/", tags=["Health"])
async def root():
    return {
        "service": "FinSight API",
        "version": "1.0.0",
        "status": "running",
        "environment": settings.ENVIRONMENT,
    }


@app.get("/health", tags=["Health"])
async def health():
    db_ok = app.state.db_pool is not None
    redis_ok = app.state.redis is not None
    return {
        "status": "healthy" if (db_ok and redis_ok) else "degraded",
        "database": "connected" if db_ok else "disconnected",
        "redis": "connected" if redis_ok else "disconnected",
    }
