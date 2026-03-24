import random
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from services import database as db
from utils.helpers import check_cooldown, set_cooldown, format_seconds

router = Router()

@router.message(Command("boss", "worldboss"))
async def cmd_boss(msg: Message):
    hero = await db.fetchone("SELECT * FROM heroes WHERE user_id=$1", msg.from_user.id)
    if not hero:
        await msg.answer("❌ Kamu belum punya hero! /start")
        return

    boss = await db.fetchone("SELECT * FROM world_boss WHERE is_active=TRUE")
    if not boss:
        await msg.answer("😴 Tidak ada world boss aktif saat ini.\nTunggu event berikutnya!")
        return

    cd = await check_cooldown(msg.from_user.id, "boss")
    if cd > 0:
        await msg.answer(f"⏳ Cooldown boss: <b>{format_seconds(cd)}</b>")
        return

    weapon_atk = await db.fetchval("""
        SELECT COALESCE(SUM(w.atk_bonus),0) FROM weapons w
        JOIN hero_weapons hw ON hw.weapon_id=w.id
        WHERE hw.user_id=$1 AND hw.equipped=TRUE
    """, msg.from_user.id) or 0

    dmg = (hero["atk"] + weapon_atk) * hero["level"] + random.randint(10, 50)
    new_hp = max(0, boss["current_hp"] - dmg)

    await db.execute("UPDATE world_boss SET current_hp=$1 WHERE id=$2", new_hp, boss["id"])
    await db.execute("""
        INSERT INTO boss_damage (user_id, boss_id, damage) VALUES ($1, $2, $3)
        ON CONFLICT (user_id, boss_id) DO UPDATE SET damage=boss_damage.damage+$3
    """, msg.from_user.id, boss["id"], dmg)

    await set_cooldown(msg.from_user.id, "boss", 3600)

    exp_reward = dmg // 2
    await db.execute("UPDATE heroes SET exp=exp+$1 WHERE user_id=$2", exp_reward, msg.from_user.id)

    pct = (new_hp / boss["max_hp"]) * 100
    bar_fill = int(pct / 10)
    hp_bar = "█" * bar_fill + "░" * (10 - bar_fill)

    text = (
        f"🐉 <b>{boss['name']}</b>\n"
        f"HP: [{hp_bar}] {pct:.1f}%\n"
        f"({new_hp:,} / {boss['max_hp']:,})\n\n"
        f"💥 Kamu serang <b>-{dmg:,}</b> damage!\n"
        f"+{exp_reward} EXP\n"
    )

    if new_hp == 0:
        # Boss mati
        await db.execute("UPDATE world_boss SET is_active=FALSE, ended_at=NOW() WHERE id=$1", boss["id"])
        top_dmg = await db.fetchall("""
            SELECT bd.damage, h.name, u.id FROM boss_damage bd
            JOIN heroes h ON h.user_id=bd.user_id
            JOIN users u ON u.id=bd.user_id
            WHERE bd.boss_id=$1 ORDER BY bd.damage DESC LIMIT 3
        """, boss["id"])

        text += f"\n💀 <b>BOSS DIKALAHKAN!</b>\n\nTop Damage:\n"
        medals = ["🥇","🥈","🥉"]
        for i, row in enumerate(top_dmg):
            reward_gold = [1000, 500, 250][i]
            text += f"{medals[i]} {row['name']} — {row['damage']:,} dmg (+{reward_gold}g)\n"
            await db.execute("UPDATE heroes SET gold=gold+$1 WHERE user_id=$2", reward_gold, row["id"])

        # Broadcast
        users = await db.fetchall("SELECT id FROM users WHERE is_banned=FALSE")
        for u in users:
            try:
                await msg.bot.send_message(u["id"], f"💀 World Boss <b>{boss['name']}</b> telah dikalahkan! Lihat /boss")
            except Exception:
                pass

    if boss.get("photo_id"):
        await msg.answer_photo(boss["photo_id"], caption=text)
    else:
        await msg.answer(text)
