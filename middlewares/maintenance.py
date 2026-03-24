import os
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Any
from services import database as db

ADMIN_IDS = set(map(int, filter(None, os.getenv("ADMIN_IDS", "").split(","))))

class MaintenanceMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable, event: Any, data: dict) -> Any:
        user = data.get("event_from_user")
        if user and user.id in ADMIN_IDS:
            return await handler(event, data)

        val = await db.fetchval("SELECT value FROM settings WHERE key='maintenance'")
        if val == "true":
            msg = "🔧 <b>Bot sedang maintenance.</b>\nSilakan kembali beberapa saat lagi!"
            if isinstance(event, Message):
                await event.answer(msg)
            elif isinstance(event, CallbackQuery):
                await event.answer("Bot sedang maintenance!", show_alert=True)
            return

        return await handler(event, data)
