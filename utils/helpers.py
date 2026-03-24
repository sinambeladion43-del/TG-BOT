import os
import random
from services import database as db

ADMIN_IDS = set(map(int, filter(None, os.getenv("ADMIN_IDS", "").split(","))))

RARITY_EMOJI = {
    "common": "⬜",
    "uncommon": "🟩",
    "rare": "🟦",
    "epic": "🟪",
    "legendary": "🟨"
}

CLASS_EMOJI = {
    "warrior": "⚔️",
    "mage": "🔮",
    "archer": "🏹"
}

CLASS_BONUS = {
    "warrior": {"hp": 30, "atk": 5, "def": 10, "spd": 0},
    "mage":    {"hp": 0,  "atk": 15, "def": 2, "spd": 3},
    "archer":  {"hp": 10, "atk": 10, "def": 3, "spd": 10},
}

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def get_battle_power(hero: dict) -> int:
    return hero["atk"] * hero["level"] + hero["def"] + hero["hp"] // 10

def exp_to_next(level: int) -> int:
    return int(100 * (level ** 1.5))

async def check_cooldown(user_id: int, action: str) -> int:
    row = await db.fetchone(
        "SELECT expires_at FROM cooldowns WHERE user_id=$1 AND action=$2",
        user_id, action
    )
    if row:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        diff = (row["expires_at"] - now).total_seconds()
        if diff > 0:
            return int(diff)
    return 0

async def set_cooldown(user_id: int, action: str, seconds: int):
    from datetime import datetime, timezone, timedelta
    expires = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    await db.execute("""
        INSERT INTO cooldowns (user_id, action, expires_at)
        VALUES ($1, $2, $3)
        ON CONFLICT (user_id, action) DO UPDATE SET expires_at=EXCLUDED.expires_at
    """, user_id, action, expires)

def format_seconds(secs: int) -> str:
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    parts = []
    if h: parts.append(f"{h}j")
    if m: parts.append(f"{m}m")
    if s: parts.append(f"{s}d")
    return " ".join(parts) or "0d"

def loot_roll(rarity_weights=None):
    if not rarity_weights:
        rarity_weights = {"common": 50, "uncommon": 30, "rare": 15, "epic": 4, "legendary": 1}
    total = sum(rarity_weights.values())
    r = random.randint(1, total)
    cumulative = 0
    for rarity, weight in rarity_weights.items():
        cumulative += weight
        if r <= cumulative:
            return rarity
    return "common"

async def log_admin_action(admin_id: int, action: str, target: str, detail: str):
    await db.execute(
        "INSERT INTO admin_logs (admin_id, action, target, detail) VALUES ($1, $2, $3, $4)",
        admin_id, action, target, detail
    )

async def send_to_log_channel(bot, text: str):
    log_channel = os.getenv("LOG_CHANNEL_ID")
    if log_channel:
        try:
            await bot.send_message(int(log_channel), text)
        except Exception:
            pass
