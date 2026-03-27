"""
Transactions API — CRUD with pagination, filtering, and category correction.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

from api.auth import CurrentUser, get_current_user

router = APIRouter()
logger = logging.getLogger("finsight.transactions")


class TransactionModel(BaseModel):
    id: Optional[UUID] = None
    user_id: Optional[str] = None
    fingerprint: Optional[str] = None
    amount: float
    direction: str  # credit | debit
    merchant: str
    merchant_raw: Optional[str] = None
    bank: Optional[str] = None
    payment_method: Optional[str] = None
    upi_ref: Optional[str] = None
    account_last4: Optional[str] = None
    transaction_date: datetime
    balance_after: Optional[float] = None
    source: str = "sms"  # sms | notification | merged | dataset
    category: str = "uncategorized"
    category_confidence: Optional[float] = None
    rl_adjusted: bool = False
    fraud_score: float = 0.0
    anomaly_score: float = 0.0
    is_subscription: bool = False
    sync_mode: Optional[str] = None
    created_at: Optional[datetime] = None


class TransactionListResponse(BaseModel):
    transactions: List[TransactionModel]
    total: int
    page: int
    page_size: int
    has_more: bool


class CategoryCorrectionRequest(BaseModel):
    transaction_id: str
    old_category: str
    new_category: str


@router.get("/transactions", response_model=TransactionListResponse)
async def list_transactions(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    direction: Optional[str] = None,
    merchant: Optional[str] = None,
    source: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    user: CurrentUser = Depends(get_current_user),
):
    """Paginated transaction list with filters."""
    db_pool = request.app.state.db_pool
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    offset = (page - 1) * page_size
    conditions = ["user_id = $1"]
    params: list = [user.user_id]
    idx = 2

    if category:
        conditions.append(f"category = ${idx}")
        params.append(category)
        idx += 1
    if direction:
        conditions.append(f"direction = ${idx}")
        params.append(direction)
        idx += 1
    if merchant:
        conditions.append(f"merchant ILIKE ${idx}")
        params.append(f"%{merchant}%")
        idx += 1
    if source:
        conditions.append(f"source = ${idx}")
        params.append(source)
        idx += 1
    if date_from:
        conditions.append(f"transaction_date >= ${idx}::timestamptz")
        params.append(date_from)
        idx += 1
    if date_to:
        conditions.append(f"transaction_date <= ${idx}::timestamptz")
        params.append(date_to)
        idx += 1
    if search:
        conditions.append(f"(merchant ILIKE ${idx} OR merchant_raw ILIKE ${idx})")
        params.append(f"%{search}%")
        idx += 1

    where = " AND ".join(conditions)

    try:
        async with db_pool.acquire() as conn:
            count_query = f"SELECT COUNT(*) FROM transactions WHERE {where}"
            total = await conn.fetchval(count_query, *params)

            data_query = f"""
                SELECT * FROM transactions 
                WHERE {where}
                ORDER BY transaction_date DESC
                LIMIT ${idx} OFFSET ${idx + 1}
            """
            params.extend([page_size, offset])
            rows = await conn.fetch(data_query, *params)

        transactions = [TransactionModel(**dict(r)) for r in rows]
        return TransactionListResponse(
            transactions=transactions,
            total=total,
            page=page,
            page_size=page_size,
            has_more=(offset + page_size) < total,
        )

    except Exception as e:
        logger.error("Transaction list failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch transactions")


@router.get("/transactions/categories")
async def get_user_categories(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """Get all unique categories used by the user."""
    db_pool = request.app.state.db_pool
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT DISTINCT category FROM transactions WHERE user_id = $1",
                user.user_id,
            )
            categories = [row["category"] for row in rows if row["category"]]
            return {"categories": categories}
    except Exception as e:
        logger.error("Failed to fetch user categories: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch categories")

@router.get("/transactions/{transaction_id}", response_model=TransactionModel)
async def get_transaction(
    request: Request,
    transaction_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Get a single transaction by ID."""
    db_pool = request.app.state.db_pool
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM transactions WHERE id = $1 AND user_id = $2",
                transaction_id, user.user_id,
            )
        if not row:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return TransactionModel(**dict(row))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Transaction fetch failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch transaction")


@router.post("/transactions/correct-category")
async def correct_category(
    request: Request,
    body: CategoryCorrectionRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """
    User corrects a transaction category — feeds RL reward signal.
    Old category gets -1.0 reward, new category gets +1.0 reward.
    """
    db_pool = request.app.state.db_pool
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        async with db_pool.acquire() as conn:
            # Update the transaction category
            result = await conn.execute(
                """UPDATE transactions 
                   SET category = $1, rl_adjusted = TRUE 
                   WHERE id = $2 AND user_id = $3""",
                body.new_category, body.transaction_id, user.user_id,
            )
            if result == "UPDATE 0":
                raise HTTPException(status_code=404, detail="Transaction not found")

            # Record feedback event for RL
            await conn.execute(
                """INSERT INTO feedback_events 
                   (user_id, event_type, target_id, old_value, new_value, reward)
                   VALUES ($1, 'category_correction', $2::uuid, $3, $4, -1.0)""",
                user.user_id, body.transaction_id, body.old_category, body.new_category,
            )
            await conn.execute(
                """INSERT INTO feedback_events 
                   (user_id, event_type, target_id, old_value, new_value, reward)
                   VALUES ($1, 'category_correction', $2::uuid, $3, $4, 1.0)""",
                user.user_id, body.transaction_id, body.old_category, body.new_category,
            )

        return {"status": "corrected", "transaction_id": body.transaction_id, "new_category": body.new_category}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Category correction failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to correct category")


class ManualTransactionRequest(BaseModel):
    amount: float
    direction: str  # credit | debit
    merchant: str
    category: str = "uncategorized"
    payment_method: Optional[str] = None
    bank: Optional[str] = None
    transaction_date: Optional[str] = None  # ISO 8601
    notes: Optional[str] = None


@router.post("/transactions/create")
async def create_transaction(
    request: Request,
    body: ManualTransactionRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """Manually create a transaction."""
    db_pool = request.app.state.db_pool
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    import hashlib
    fp_string = f"{user.user_id}|{body.merchant}|{body.amount}|{body.transaction_date or ''}"
    fingerprint = hashlib.sha256(fp_string.encode()).hexdigest()

    txn_date = datetime.utcnow()
    if body.transaction_date:
        try:
            txn_date = datetime.fromisoformat(body.transaction_date)
        except ValueError:
            pass

    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO transactions
                (user_id, fingerprint, amount, direction, merchant, merchant_raw,
                 bank, payment_method, transaction_date, source,
                 category, category_confidence, sync_mode)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::timestamptz,
                        'manual', $10, 1.0, 'manual')
                ON CONFLICT (fingerprint) DO NOTHING
                RETURNING *""",
                user.user_id, fingerprint, body.amount, body.direction,
                body.merchant, body.notes or body.merchant,
                body.bank, body.payment_method,
                txn_date, body.category,
            )
            if row:
                return {"status": "created", "transaction": dict(row)}
            else:
                return {"status": "duplicate"}
    except Exception as e:
        logger.error("Manual transaction creation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create transaction")

