import logging
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from services import database as db

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="Asia/Jakarta")

async def daily_reset(bot):
    logger.info("Running daily reset...")
    await db.execute("DELETE FROM cooldowns WHERE action='dungeon' OR action='daily' OR action='duel'")
    all_users = await db.fetchall("SELECT id FROM users WHERE is_banned=FALSE")
    count = 0
    for u in all_users:
        try:
            await bot.send_message(u["id"],
                "🌅 <b>Reset Harian!</b>\n\n"
                "✅ Cooldown dungeon direset\n"
                "✅ Daily quest tersedia\n"
                "✅ Duel tersedia kembali\n\n"
                "Gunakan /daily untuk klaim reward harian! 🎁"
            )
            count += 1
        except Exception:
            pass
    logger.info(f"Daily reset done. Notified {count} users.")

async def check_guild_wars(bot):
    wars = await db.fetchall("SELECT * FROM guild_wars WHERE status='active'")
    for war in wars:
        guild_a = await db.fetchone("SELECT * FROM guilds WHERE id=$1", war["guild_a"])
        guild_b = await db.fetchone("SELECT * FROM guilds WHERE id=$1", war["guild_b"])
        if not guild_a or not guild_b:
            continue
        score_a = await db.fetchval(
            "SELECT COALESCE(SUM(battle_power),0) FROM heroes WHERE guild_id=$1", war["guild_a"]
        ) or 0
        score_b = await db.fetchval(
            "SELECT COALESCE(SUM(battle_power),0) FROM heroes WHERE guild_id=$1", war["guild_b"]
        ) or 0
        winner_id = war["guild_a"] if score_a >= score_b else war["guild_b"]
        loser_id = war["guild_b"] if score_a >= score_b else war["guild_a"]
        winner = guild_a if score_a >= score_b else guild_b

        await db.execute(
            "UPDATE guild_wars SET status='ended', score_a=$1, score_b=$2, winner_id=$3, ended_at=NOW() WHERE id=$4",
            score_a, score_b, winner_id, war["id"]
        )
        await db.execute("UPDATE guilds SET wins=wins+1 WHERE id=$1", winner_id)
        await db.execute("UPDATE guilds SET losses=losses+1 WHERE id=$1", loser_id)
        await db.execute("UPDATE heroes SET gold=gold+100 WHERE guild_id=$1", winner_id)

        msg = (
            f"⚔️ <b>Guild War Selesai!</b>\n\n"
            f"🏰 {guild_a['name']}: {score_a:,} power\n"
            f"🏰 {guild_b['name']}: {score_b:,} power\n\n"
            f"🏆 Pemenang: <b>{winner['name']}</b>\n"
            f"💰 Semua anggota pemenang mendapat +100 gold!"
        )
        for gid in [war["guild_a"], war["guild_b"]]:
            members = await db.fetchall("SELECT user_id FROM heroes WHERE guild_id=$1", gid)
            for m in members:
                try:
                    await bot.send_message(m["user_id"], msg)
                except Exception:
                    pass

async def world_boss_reminder(bot):
    boss = await db.fetchone("SELECT * FROM world_boss WHERE is_active=TRUE")
    if boss:
        users = await db.fetchall("SELECT id FROM users WHERE is_banned=FALSE")
        for u in users:
            try:
                await bot.send_message(u["id"],
                    f"🐉 <b>World Boss Aktif!</b>\n\n"
                    f"<b>{boss['name']}</b> masih berkeliaran!\n"
                    f"HP Sisa: <b>{boss['current_hp']:,}</b>\n\n"
                    f"Gunakan /boss untuk menyerang! 🗡️"
                )
            except Exception:
                pass

async def start_scheduler(bot):
    # Daily reset jam 00:00 WIB
    scheduler.add_job(daily_reset, CronTrigger(hour=0, minute=0), args=[bot], id="daily_reset")
    # Guild war check setiap Minggu jam 21:00 WIB
    scheduler.add_job(check_guild_wars, CronTrigger(day_of_week="sun", hour=21, minute=0), args=[bot], id="guild_war")
    # World boss reminder setiap 6 jam
    scheduler.add_job(world_boss_reminder, CronTrigger(hour="0,6,12,18", minute=0), args=[bot], id="boss_reminder")
    scheduler.start()
    logger.info("Scheduler started.")
