from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from services import database as db

router = Router()

@router.message(Command("war", "guildwar"))
async def cmd_war(msg: Message):
    hero = await db.fetchone("SELECT * FROM heroes WHERE user_id=$1", msg.from_user.id)
    if not hero or not hero["guild_id"]:
        await msg.answer("❌ Kamu harus bergabung guild dulu!")
        return

    guild = await db.fetchone("SELECT * FROM guilds WHERE id=$1", hero["guild_id"])
    if guild["leader_id"] != msg.from_user.id:
        await msg.answer("❌ Hanya guild leader yang bisa declare war!")
        return

    active = await db.fetchone("""
        SELECT * FROM guild_wars
        WHERE (guild_a=$1 OR guild_b=$1) AND status='active'
    """, hero["guild_id"])

    if active:
        other_id = active["guild_b"] if active["guild_a"] == hero["guild_id"] else active["guild_a"]
        other = await db.fetchone("SELECT name FROM guilds WHERE id=$1", other_id)
        my_power = await db.fetchval(
            "SELECT COALESCE(SUM(atk*level+def+hp/10),0) FROM heroes WHERE guild_id=$1", hero["guild_id"]
        ) or 0
        enemy_power = await db.fetchval(
            "SELECT COALESCE(SUM(atk*level+def+hp/10),0) FROM heroes WHERE guild_id=$1", other_id
        ) or 0

        kb = InlineKeyboardBuilder()
        kb.button(text="⚔️ Selesaikan War Sekarang", callback_data=f"end_war_{active['id']}")
        await msg.answer(
            f"⚔️ <b>Guild War Aktif!</b>\n\n"
            f"VS: <b>{other['name']}</b>\n"
            f"Power Kamu: {my_power:,}\n"
            f"Power Musuh: {enemy_power:,}\n\n"
            f"War akan selesai otomatis Minggu malam.",
            reply_markup=kb.as_markup()
        )
        return

    # Cari lawan
    enemies = await db.fetchall("""
        SELECT g.id, g.name, COUNT(h.user_id) as members,
               COALESCE(SUM(h.atk*h.level+h.def+h.hp/10),0) as power
        FROM guilds g LEFT JOIN heroes h ON h.guild_id=g.id
        WHERE g.id != $1
        GROUP BY g.id ORDER BY ABS(power - $2) LIMIT 8
    """, hero["guild_id"],
        await db.fetchval("SELECT COALESCE(SUM(atk*level+def+hp/10),0) FROM heroes WHERE guild_id=$1", hero["guild_id"]) or 0
    )

    kb = InlineKeyboardBuilder()
    lines = ["⚔️ <b>Pilih Musuh untuk Guild War</b>\n"]
    for e in enemies:
        lines.append(f"🏰 <b>{e['name']}</b> | ⚡{e['power']:,} power | 👥{e['members']} member")
        kb.button(text=f"⚔️ Serang {e['name']}", callback_data=f"declare_war_{hero['guild_id']}_{e['id']}")
    kb.adjust(1)
    await msg.answer("\n".join(lines), reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("declare_war_"))
async def cb_declare_war(cb: CallbackQuery):
    parts = cb.data.split("_")
    my_guild_id = int(parts[2])
    enemy_guild_id = int(parts[3])

    existing = await db.fetchone("""
        SELECT id FROM guild_wars
        WHERE (guild_a=$1 OR guild_b=$1) AND status='active'
    """, my_guild_id)
    if existing:
        await cb.answer("Guild kamu sudah dalam war!", show_alert=True)
        return

    my_guild = await db.fetchone("SELECT * FROM guilds WHERE id=$1", my_guild_id)
    enemy_guild = await db.fetchone("SELECT * FROM guilds WHERE id=$1", enemy_guild_id)

    war = await db.fetchone("""
        INSERT INTO guild_wars (guild_a, guild_b, status)
        VALUES ($1, $2, 'active') RETURNING id
    """, my_guild_id, enemy_guild_id)

    # Notif ke enemy leader
    try:
        await cb.bot.send_message(
            enemy_guild["leader_id"],
            f"⚔️ <b>GUILD WAR DIMULAI!</b>\n\n"
            f"Guild <b>{my_guild['name']}</b> menyerang guild kamu!\n"
            f"Gunakan /war untuk lihat status."
        )
    except Exception:
        pass

    # Broadcast ke semua member guild penyerang
    members = await db.fetchall("SELECT user_id FROM heroes WHERE guild_id=$1", my_guild_id)
    for m in members:
        try:
            await cb.bot.send_message(m["user_id"],
                f"⚔️ <b>Guild War Dimulai!</b>\n"
                f"VS <b>{enemy_guild['name']}</b>\n"
                f"Tingkatkan power heromu! War selesai Minggu malam."
            )
        except Exception:
            pass

    await cb.message.edit_text(
        f"⚔️ <b>PERANG DIMULAI!</b>\n\n"
        f"🏰 {my_guild['name']} VS {enemy_guild['name']}\n\n"
        f"War akan berlangsung hingga Minggu malam.\n"
        f"Kumpulkan battle power sebanyak mungkin!"
    )

@router.callback_query(F.data.startswith("end_war_"))
async def cb_end_war(cb: CallbackQuery):
    war_id = int(cb.data.split("_")[2])
    war = await db.fetchone("SELECT * FROM guild_wars WHERE id=$1", war_id)
    if not war:
        await cb.answer("War tidak ditemukan!", show_alert=True)
        return

    guild_a = await db.fetchone("SELECT * FROM guilds WHERE id=$1", war["guild_a"])
    guild_b = await db.fetchone("SELECT * FROM guilds WHERE id=$1", war["guild_b"])

    score_a = await db.fetchval(
        "SELECT COALESCE(SUM(atk*level+def+hp/10),0) FROM heroes WHERE guild_id=$1", war["guild_a"]
    ) or 0
    score_b = await db.fetchval(
        "SELECT COALESCE(SUM(atk*level+def+hp/10),0) FROM heroes WHERE guild_id=$1", war["guild_b"]
    ) or 0

    winner_id = war["guild_a"] if score_a >= score_b else war["guild_b"]
    winner = guild_a if score_a >= score_b else guild_b
    loser_id = war["guild_b"] if score_a >= score_b else war["guild_a"]

    await db.execute("""
        UPDATE guild_wars SET status='ended', score_a=$1, score_b=$2, winner_id=$3, ended_at=NOW()
        WHERE id=$4
    """, score_a, score_b, winner_id, war_id)
    await db.execute("UPDATE guilds SET wins=wins+1 WHERE id=$1", winner_id)
    await db.execute("UPDATE guilds SET losses=losses+1 WHERE id=$1", loser_id)
    await db.execute("UPDATE heroes SET gold=gold+150 WHERE guild_id=$1", winner_id)

    recap = (
        f"⚔️ <b>Hasil Guild War!</b>\n\n"
        f"🏰 {guild_a['name']}: {score_a:,} power\n"
        f"🏰 {guild_b['name']}: {score_b:,} power\n\n"
        f"🏆 Pemenang: <b>{winner['name']}</b>\n"
        f"💰 Semua anggota pemenang mendapat +150 gold!"
    )

    for gid in [war["guild_a"], war["guild_b"]]:
        members = await db.fetchall("SELECT user_id FROM heroes WHERE guild_id=$1", gid)
        for m in members:
            try:
                await cb.bot.send_message(m["user_id"], recap)
            except Exception:
                pass

    await cb.message.edit_text(recap)
