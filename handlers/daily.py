import random
from datetime import date
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from services import database as db

router = Router()

DAILY_REWARDS = [
    {"day": 1,  "gold": 100,  "exp": 50,  "gem": 0},
    {"day": 2,  "gold": 150,  "exp": 75,  "gem": 0},
    {"day": 3,  "gold": 200,  "exp": 100, "gem": 1},
    {"day": 4,  "gold": 250,  "exp": 125, "gem": 0},
    {"day": 5,  "gold": 300,  "exp": 150, "gem": 1},
    {"day": 6,  "gold": 400,  "exp": 200, "gem": 1},
    {"day": 7,  "gold": 600,  "exp": 300, "gem": 3},
]

@router.message(Command("daily", "klaim"))
async def cmd_daily(msg: Message):
    hero = await db.fetchone("SELECT * FROM heroes WHERE user_id=$1", msg.from_user.id)
    if not hero:
        await msg.answer("❌ Kamu belum punya hero! /start")
        return

    log = await db.fetchone("SELECT * FROM daily_logs WHERE user_id=$1", msg.from_user.id)
    today = date.today()

    if log:
        if log["last_daily"] == today:
            await msg.answer("⏳ Kamu sudah klaim daily hari ini!\nKembali besok.")
            return
        streak = log["streak"] + 1 if log["last_daily"] == today.replace(day=today.day - 1) else 1
        await db.execute(
            "UPDATE daily_logs SET last_daily=$1, streak=$2 WHERE user_id=$3",
            today, streak, msg.from_user.id
        )
    else:
        streak = 1
        await db.execute(
            "INSERT INTO daily_logs (user_id, last_daily, streak) VALUES ($1, $2, 1)",
            msg.from_user.id, today
        )

    day_index = min(streak - 1, 6)
    reward = DAILY_REWARDS[day_index]

    # Bonus jika menikah
    marriage = await db.fetchone(
        "SELECT id FROM marriages WHERE user_a=$1 OR user_b=$1", msg.from_user.id
    )
    bonus_gold = 50 if marriage else 0
    total_gold = reward["gold"] + bonus_gold

    await db.execute(
        "UPDATE heroes SET gold=gold+$1, exp=exp+$2, gems=gems+$3 WHERE user_id=$4",
        total_gold, reward["exp"], reward["gem"], msg.from_user.id
    )

    text = (
        f"🌅 <b>Daily Login!</b>\n"
        f"{'─'*20}\n"
        f"🔥 Streak: <b>{streak} hari</b>\n"
        f"{'─'*20}\n"
        f"💰 Gold: +<b>{total_gold}</b>"
        + (f" (+{bonus_gold} bonus nikah 💑)" if bonus_gold else "") +
        f"\n⭐ EXP: +<b>{reward['exp']}</b>"
        + (f"\n💎 Gems: +<b>{reward['gem']}</b>" if reward["gem"] else "") +
        f"\n{'─'*20}\n"
    )

    # Show streak calendar
    cal = []
    for i in range(7):
        if i < streak % 7:
            cal.append("✅")
        elif i == streak % 7 - 1 or (streak % 7 == 0 and i == 6):
            cal.append("🌟")
        else:
            cal.append("⬜")
    text += "Streak: " + " ".join(cal)

    if streak >= 7:
        text += f"\n\n🎊 <b>Streak 7 hari!</b> Bonus double besok!"

    await msg.answer(text)
