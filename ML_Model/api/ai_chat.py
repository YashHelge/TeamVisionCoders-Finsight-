"""
AI Chat API — SSE streaming chat with Groq Llama 3.3 70B.
"""

import logging
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.auth import CurrentUser, get_current_user
from config import settings

router = APIRouter()
logger = logging.getLogger("finsight.ai_chat")


class ChatMessage(BaseModel):
    role: str  # user | assistant
    content: str


class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []
    include_web: bool = False


class ChatResponse(BaseModel):
    role: str = "assistant"
    content: str


@router.post("/ai/chat")
async def ai_chat(
    request: Request,
    body: ChatRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """
    Streaming SSE chat with Groq Llama 3.3 70B.
    System prompt injects user's financial profile.
    """
    db_pool = request.app.state.db_pool
    redis_client = request.app.state.redis

    # Build financial context for system prompt
    financial_context = await _build_financial_context(db_pool, user.user_id)

    # Optional web augmentation
    web_context = ""
    if body.include_web:
        try:
            from web_augmentor import augment_query
            web_context = await augment_query(body.message)
        except Exception as e:
            logger.warning("Web augmentation failed: %s", e)

    system_prompt = f"""You are FinSight AI — a personal finance assistant for Indian users. 
You have access to the user's complete financial profile:

{financial_context}

{f'Additional web context: {web_context}' if web_context else ''}

Guidelines:
- Provide specific, actionable financial advice based on the user's actual data
- Reference their specific transactions, spending patterns, and subscriptions
- Use Indian Rupee (₹) formatting
- Be concise but thorough
- If asked about current rates/policies, mention that data may not be real-time
- Never make up transaction data — only reference what's in their profile
"""

    # Build messages
    messages = [{"role": "system", "content": system_prompt}]
    for msg in body.history[-20:]:  # Last 20 messages for context
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": body.message})

    # Check semantic cache
    if redis_client:
        try:
            from groq_client import check_semantic_cache
            cached_response = await check_semantic_cache(redis_client, user.user_id, body.message)
            if cached_response:
                return ChatResponse(content=cached_response)
        except Exception:
            pass

    # Stream from Groq
    try:
        from groq_client import stream_chat, GroqCircuitOpen
        
        async def event_generator():
            full_response = ""
            try:
                async for chunk in stream_chat(messages):
                    full_response += chunk
                    yield f"data: {json.dumps({'content': chunk})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"

                # Save to chat history
                if db_pool:
                    try:
                        async with db_pool.acquire() as conn:
                            await conn.execute(
                                """INSERT INTO chat_history (user_id, role, content)
                                VALUES ($1, 'user', $2), ($1, 'assistant', $3)""",
                                user.user_id, body.message, full_response,
                            )
                    except Exception:
                        pass

                # Cache response
                if redis_client and full_response:
                    try:
                        from groq_client import cache_response
                        await cache_response(redis_client, user.user_id, body.message, full_response)
                    except Exception:
                        pass

            except GroqCircuitOpen:
                yield f"data: {json.dumps({'content': 'AI service is temporarily unavailable. Please try again in a minute.', 'done': True})}\n\n"
            except Exception as e:
                logger.error("Groq streaming failed: %s", e)
                yield f"data: {json.dumps({'content': 'An error occurred. Please try again.', 'done': True, 'error': True})}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    except Exception as e:
        logger.error("AI chat failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="AI service unavailable")


@router.get("/ai/history")
async def get_chat_history(
    request: Request,
    limit: int = 50,
    user: CurrentUser = Depends(get_current_user),
):
    """Fetch recent chat history."""
    db_pool = request.app.state.db_pool
    if not db_pool:
        return {"history": []}

    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT role, content, created_at FROM chat_history
                WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2""",
                user.user_id, limit,
            )
        return {"history": [dict(r) for r in reversed(rows)]}
    except Exception as e:
        logger.error("Chat history fetch failed: %s", e)
        return {"history": []}


async def _build_financial_context(db_pool, user_id: str) -> str:
    """Build a financial profile summary for the AI system prompt."""
    if not db_pool:
        return "No financial data available yet."

    try:
        async with db_pool.acquire() as conn:
            # Last 30 days summary
            summary = await conn.fetchrow(
                """SELECT 
                    COUNT(*) as txn_count,
                    COALESCE(SUM(CASE WHEN direction='credit' THEN amount ELSE 0 END), 0) as income,
                    COALESCE(SUM(CASE WHEN direction='debit' THEN amount ELSE 0 END), 0) as expense
                FROM transactions 
                WHERE user_id = $1 AND transaction_date >= NOW() - INTERVAL '30 days'""",
                user_id,
            )

            # Category breakdown
            categories = await conn.fetch(
                """SELECT category, COUNT(*) as cnt, SUM(amount) as total
                FROM transactions 
                WHERE user_id = $1 AND direction='debit' 
                      AND transaction_date >= NOW() - INTERVAL '30 days'
                GROUP BY category ORDER BY total DESC LIMIT 8""",
                user_id,
            )

            # Active subscriptions
            subs = await conn.fetch(
                """SELECT merchant, avg_monthly_cost, category
                FROM subscriptions 
                WHERE user_id = $1 AND is_active = TRUE
                ORDER BY avg_monthly_cost DESC LIMIT 10""",
                user_id,
            )

            # Recent transactions
            recent = await conn.fetch(
                """SELECT amount, direction, merchant, category, transaction_date
                FROM transactions 
                WHERE user_id = $1 
                ORDER BY transaction_date DESC LIMIT 10""",
                user_id,
            )

        income = float(summary["income"])
        expense = float(summary["expense"])
        savings_rate = ((income - expense) / income * 100) if income > 0 else 0

        ctx = f"""FINANCIAL PROFILE (Last 30 days):
- Transactions: {summary['txn_count']}
- Total Income: ₹{income:,.2f}
- Total Expense: ₹{expense:,.2f}
- Net Flow: ₹{income - expense:,.2f}
- Savings Rate: {savings_rate:.1f}%

SPENDING BY CATEGORY:
"""
        for c in categories:
            ctx += f"- {c['category']}: ₹{float(c['total']):,.2f} ({c['cnt']} txns)\n"

        if subs:
            ctx += f"\nACTIVE SUBSCRIPTIONS ({len(subs)}):\n"
            total_sub = 0
            for s in subs:
                ctx += f"- {s['merchant']} ({s['category']}): ₹{float(s['avg_monthly_cost']):,.2f}/month\n"
                total_sub += float(s["avg_monthly_cost"])
            ctx += f"Total Monthly Subscriptions: ₹{total_sub:,.2f}\n"

        if recent:
            ctx += "\nRECENT TRANSACTIONS:\n"
            for r in recent:
                direction = "+" if r["direction"] == "credit" else "-"
                ctx += f"- {direction}₹{float(r['amount']):,.2f} | {r['merchant']} | {r['category']} | {r['transaction_date']}\n"

        return ctx

    except Exception as e:
        logger.warning("Financial context build failed: %s", e)
        return "Financial data temporarily unavailable."
