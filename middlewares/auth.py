from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from services import database as db
from typing import Callable, Awaitable, Any

class AuthMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable, event: Any, data: dict) -> Any:
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        # Upsert user
        await db.execute("""
            INSERT INTO users (id, username, full_name, last_active)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (id) DO UPDATE SET
                username=EXCLUDED.username,
                full_name=EXCLUDED.full_name,
                last_active=NOW()
        """, user.id, user.username, user.full_name)

        # Check ban
        row = await db.fetchone("SELECT is_banned, ban_reason FROM users WHERE id=$1", user.id)
        if row and row["is_banned"]:
            msg = f"🚫 Akunmu telah dibanned.\nAlasan: {row['ban_reason'] or 'Melanggar aturan'}"
            if isinstance(event, Message):
                await event.answer(msg)
            elif isinstance(event, CallbackQuery):
                await event.answer(msg, show_alert=True)
            return

        return await handler(event, data)
