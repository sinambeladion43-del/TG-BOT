from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from services import database as db

router = Router()

class GuildState(StatesGroup):
    creating_name = State()
    creating_desc = State()
    setting_announce = State()

def guild_kb(guild, user_id, is_leader=False):
    kb = InlineKeyboardBuilder()
    kb.button(text="👥 Anggota", callback_data=f"guild_members_{guild['id']}")
    kb.button(text="📊 Info", callback_data=f"guild_info_{guild['id']}")
    if is_leader:
        kb.button(text="📢 Pengumuman", callback_data=f"guild_announce_{guild['id']}")
        kb.button(text="🚪 Kick Member", callback_data=f"guild_kick_menu_{guild['id']}")
        kb.button(text="🤝 Aliansi", callback_data=f"guild_alliance_{guild['id']}")
    kb.button(text="🚶 Keluar Guild", callback_data=f"guild_leave_{guild['id']}")
    kb.adjust(2)
    return kb.as_markup()

@router.message(Command("guild", "g"))
async def cmd_guild(msg: Message):
    hero = await db.fetchone("SELECT * FROM heroes WHERE user_id=$1", msg.from_user.id)
    if not hero:
        await msg.answer("❌ Kamu belum punya hero! /start")
        return

    if not hero["guild_id"]:
        kb = InlineKeyboardBuilder()
        kb.button(text="➕ Buat Guild", callback_data="guild_create")
        kb.button(text="🔍 Cari Guild", callback_data="guild_search")
        kb.adjust(2)
        await msg.answer(
            "🏰 <b>Kamu belum bergabung guild.</b>\n\nBuat guild baru atau cari guild!",
            reply_markup=kb.as_markup()
        )
        return

    guild = await db.fetchone("SELECT * FROM guilds WHERE id=$1", hero["guild_id"])
    if not guild:
        await db.execute("UPDATE heroes SET guild_id=NULL WHERE user_id=$1", msg.from_user.id)
        await cmd_guild(msg)
        return

    is_leader = guild["leader_id"] == msg.from_user.id
    member_count = await db.fetchval("SELECT COUNT(*) FROM heroes WHERE guild_id=$1", guild["id"])
    total_power = await db.fetchval("SELECT COALESCE(SUM(atk*level+def+hp/10),0) FROM heroes WHERE guild_id=$1", guild["id"]) or 0
    alliance = None
    if guild.get("alliance_with"):
        alliance = await db.fetchone("SELECT name FROM guilds WHERE id=$1", guild["alliance_with"])

    text = (
        f"🏰 <b>{guild['name']}</b>"
        f"{' 👑' if is_leader else ''}\n"
        f"{'─'*22}\n"
        f"📝 {guild['description']}\n"
        f"{'─'*22}\n"
        f"⭐ Level: {guild['level']} | 👥 Anggota: {member_count}/{guild['max_members']}\n"
        f"⚡ Total Power: {total_power:,}\n"
        f"🏆 W/L: {guild['wins']}/{guild['losses']}\n"
    )
    if alliance:
        text += f"🤝 Aliansi: {alliance['name']}\n"
    if guild.get("announcement"):
        text += f"{'─'*22}\n📢 {guild['announcement']}\n"

    if guild.get("photo_id"):
        await msg.answer_photo(guild["photo_id"], caption=text, reply_markup=guild_kb(guild, msg.from_user.id, is_leader))
    else:
        await msg.answer(text, reply_markup=guild_kb(guild, msg.from_user.id, is_leader))

@router.callback_query(F.data == "guild_create")
async def cb_guild_create(cb: CallbackQuery, state: FSMContext):
    hero = await db.fetchone("SELECT * FROM heroes WHERE user_id=$1", cb.from_user.id)
    if hero and hero["guild_id"]:
        await cb.answer("Kamu sudah di guild!", show_alert=True)
        return
    if not hero or hero["level"] < 5:
        await cb.answer("Minimal level 5 untuk buat guild!", show_alert=True)
        return
    if hero["gold"] < 1000:
        await cb.answer("Butuh 1000 gold untuk buat guild!", show_alert=True)
        return
    await cb.message.edit_text("🏰 Masukkan nama guild (2-30 karakter):")
    await state.set_state(GuildState.creating_name)

@router.message(GuildState.creating_name)
async def guild_name_input(msg: Message, state: FSMContext):
    name = msg.text.strip()
    if len(name) < 2 or len(name) > 30:
        await msg.answer("❌ Nama guild 2-30 karakter.")
        return
    existing = await db.fetchone("SELECT id FROM guilds WHERE name=$1", name)
    if existing:
        await msg.answer("❌ Nama guild sudah dipakai. Coba nama lain:")
        return
    await state.update_data(guild_name=name)
    await msg.answer(f"Nama: <b>{name}</b>\nMasukkan deskripsi guild:")
    await state.set_state(GuildState.creating_desc)

@router.message(GuildState.creating_desc)
async def guild_desc_input(msg: Message, state: FSMContext):
    desc = msg.text.strip()[:200]
    data = await state.get_data()
    name = data["guild_name"]

    await db.execute("UPDATE heroes SET gold=gold-1000 WHERE user_id=$1", msg.from_user.id)
    result = await db.fetchone("""
        INSERT INTO guilds (name, description, leader_id)
        VALUES ($1, $2, $3) RETURNING id
    """, name, desc, msg.from_user.id)

    await db.execute("UPDATE heroes SET guild_id=$1 WHERE user_id=$2", result["id"], msg.from_user.id)
    await state.clear()
    await msg.answer(
        f"🎉 Guild <b>{name}</b> berhasil dibuat!\n"
        f"📝 {desc}\n\n"
        f"Bagikan kode invite: <code>/joinguild {result['id']}</code>"
    )

@router.message(Command("joinguild"))
async def cmd_join_guild(msg: Message):
    hero = await db.fetchone("SELECT * FROM heroes WHERE user_id=$1", msg.from_user.id)
    if not hero:
        await msg.answer("❌ Kamu belum punya hero!")
        return
    if hero["guild_id"]:
        await msg.answer("❌ Kamu sudah di guild! Keluar dulu.")
        return

    args = msg.text.split()
    if len(args) < 2:
        await msg.answer("Format: /joinguild [guild_id]")
        return

    try:
        guild_id = int(args[1])
    except ValueError:
        await msg.answer("❌ ID guild tidak valid.")
        return

    guild = await db.fetchone("SELECT * FROM guilds WHERE id=$1", guild_id)
    if not guild:
        await msg.answer("❌ Guild tidak ditemukan.")
        return

    count = await db.fetchval("SELECT COUNT(*) FROM heroes WHERE guild_id=$1", guild_id)
    if count >= guild["max_members"]:
        await msg.answer("❌ Guild penuh!")
        return

    await db.execute("UPDATE heroes SET guild_id=$1 WHERE user_id=$2", guild_id, msg.from_user.id)
    await db.execute("UPDATE guilds SET exp=exp+50 WHERE id=$1", guild_id)

    try:
        await msg.bot.send_message(guild["leader_id"],
            f"👤 <b>{hero['name']}</b> bergabung ke guild <b>{guild['name']}</b>!")
    except Exception:
        pass

    await msg.answer(f"✅ Berhasil bergabung ke guild <b>{guild['name']}</b>!")

@router.callback_query(F.data.startswith("guild_members_"))
async def cb_guild_members(cb: CallbackQuery):
    guild_id = int(cb.data.split("_")[2])
    members = await db.fetchall("""
        SELECT h.name, h.level, h.hero_class, u.id,
               (h.atk*h.level+h.def+h.hp/10) as bp
        FROM heroes h JOIN users u ON u.id=h.user_id
        WHERE h.guild_id=$1 ORDER BY bp DESC
    """, guild_id)
    guild = await db.fetchone("SELECT * FROM guilds WHERE id=$1", guild_id)

    lines = [f"👥 <b>Anggota {guild['name']}</b>\n"]
    for i, m in enumerate(members, 1):
        crown = "👑" if m["id"] == guild["leader_id"] else f"{i}."
        lines.append(f"{crown} {m['name']} Lv.{m['level']} | ⚡{m['bp']:,}")

    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Kembali", callback_data=f"guild_info_{guild_id}")
    await cb.message.edit_text("\n".join(lines), reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("guild_leave_"))
async def cb_guild_leave(cb: CallbackQuery):
    guild_id = int(cb.data.split("_")[2])
    guild = await db.fetchone("SELECT * FROM guilds WHERE id=$1", guild_id)
    if guild and guild["leader_id"] == cb.from_user.id:
        await cb.answer("Kamu leader! Transfer kepemimpinan atau bubarkan guild.", show_alert=True)
        return
    await db.execute("UPDATE heroes SET guild_id=NULL WHERE user_id=$1", cb.from_user.id)
    await cb.message.edit_text("✅ Kamu telah keluar dari guild.")

@router.callback_query(F.data == "guild_search")
async def cb_guild_search(cb: CallbackQuery):
    guilds = await db.fetchall("""
        SELECT g.*, COUNT(h.user_id) as members
        FROM guilds g LEFT JOIN heroes h ON h.guild_id=g.id
        GROUP BY g.id ORDER BY g.wins DESC LIMIT 10
    """)
    lines = ["🔍 <b>Daftar Guild Aktif</b>\n"]
    kb = InlineKeyboardBuilder()
    for g in guilds:
        lines.append(f"🏰 <b>{g['name']}</b> - {g['members']}/{g['max_members']} member | 🏆{g['wins']}W")
        kb.button(text=f"Gabung {g['name']}", callback_data=f"join_guild_confirm_{g['id']}")
    kb.adjust(1)
    await cb.message.edit_text("\n".join(lines), reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("join_guild_confirm_"))
async def cb_join_confirm(cb: CallbackQuery):
    guild_id = int(cb.data.split("_")[3])
    hero = await db.fetchone("SELECT * FROM heroes WHERE user_id=$1", cb.from_user.id)
    if not hero:
        await cb.answer("Belum punya hero!", show_alert=True)
        return
    if hero["guild_id"]:
        await cb.answer("Kamu sudah di guild!", show_alert=True)
        return

    guild = await db.fetchone("SELECT * FROM guilds WHERE id=$1", guild_id)
    count = await db.fetchval("SELECT COUNT(*) FROM heroes WHERE guild_id=$1", guild_id)
    if count >= guild["max_members"]:
        await cb.answer("Guild penuh!", show_alert=True)
        return

    await db.execute("UPDATE heroes SET guild_id=$1 WHERE user_id=$2", guild_id, cb.from_user.id)
    await cb.message.edit_text(f"✅ Berhasil bergabung ke guild <b>{guild['name']}</b>!\nGunakan /guild untuk info guild.")

@router.callback_query(F.data.startswith("guild_announce_"))
async def cb_set_announce(cb: CallbackQuery, state: FSMContext):
    guild_id = int(cb.data.split("_")[2])
    guild = await db.fetchone("SELECT * FROM guilds WHERE id=$1", guild_id)
    if guild["leader_id"] != cb.from_user.id:
        await cb.answer("Hanya leader yang bisa!", show_alert=True)
        return
    await state.update_data(announce_guild_id=guild_id)
    await cb.message.edit_text("📢 Masukkan pengumuman guild:")
    await state.set_state(GuildState.setting_announce)

@router.message(GuildState.setting_announce)
async def guild_announce_input(msg: Message, state: FSMContext):
    data = await state.get_data()
    guild_id = data["announce_guild_id"]
    text = msg.text.strip()[:300]
    await db.execute("UPDATE guilds SET announcement=$1 WHERE id=$2", text, guild_id)
    await state.clear()
    await msg.answer("✅ Pengumuman guild diupdate!")

@router.callback_query(F.data.startswith("guild_alliance_"))
async def cb_guild_alliance(cb: CallbackQuery):
    guild_id = int(cb.data.split("_")[2])
    guild = await db.fetchone("SELECT * FROM guilds WHERE id=$1", guild_id)
    if guild["leader_id"] != cb.from_user.id:
        await cb.answer("Hanya leader yang bisa!", show_alert=True)
        return

    others = await db.fetchall("""
        SELECT g.id, g.name FROM guilds g
        WHERE g.id != $1 AND g.id != COALESCE($2, 0)
        LIMIT 10
    """, guild_id, guild.get("alliance_with"))

    kb = InlineKeyboardBuilder()
    lines = ["🤝 <b>Pilih Guild untuk Aliansi</b>\n"]
    for g in others:
        lines.append(f"🏰 {g['name']}")
        kb.button(text=f"Aliansi dengan {g['name']}", callback_data=f"set_alliance_{guild_id}_{g['id']}")
    if guild.get("alliance_with"):
        kb.button(text="❌ Putus Aliansi", callback_data=f"break_alliance_{guild_id}")
    kb.button(text="🔙 Kembali", callback_data=f"guild_info_{guild_id}")
    kb.adjust(1)
    await cb.message.edit_text("\n".join(lines), reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("set_alliance_"))
async def cb_set_alliance(cb: CallbackQuery):
    parts = cb.data.split("_")
    guild_id = int(parts[2])
    target_id = int(parts[3])
    await db.execute("UPDATE guilds SET alliance_with=$1 WHERE id=$2", target_id, guild_id)
    target = await db.fetchone("SELECT name FROM guilds WHERE id=$1", target_id)
    await cb.answer(f"✅ Aliansi dengan {target['name']} dibentuk!")
    cb.data = f"guild_info_{guild_id}"
    await cb_guild_info(cb)

@router.callback_query(F.data.startswith("break_alliance_"))
async def cb_break_alliance(cb: CallbackQuery):
    guild_id = int(cb.data.split("_")[2])
    await db.execute("UPDATE guilds SET alliance_with=NULL WHERE id=$1", guild_id)
    await cb.answer("Aliansi diputus.")
    cb.data = f"guild_info_{guild_id}"
    await cb_guild_info(cb)

@router.callback_query(F.data.startswith("guild_info_"))
async def cb_guild_info(cb: CallbackQuery):
    guild_id = int(cb.data.split("_")[2])
    guild = await db.fetchone("SELECT * FROM guilds WHERE id=$1", guild_id)
    if not guild:
        await cb.answer("Guild tidak ditemukan!", show_alert=True)
        return
    is_leader = guild["leader_id"] == cb.from_user.id
    member_count = await db.fetchval("SELECT COUNT(*) FROM heroes WHERE guild_id=$1", guild["id"])
    total_power = await db.fetchval("SELECT COALESCE(SUM(atk*level+def+hp/10),0) FROM heroes WHERE guild_id=$1", guild["id"]) or 0
    text = (
        f"🏰 <b>{guild['name']}</b>\n"
        f"📝 {guild['description']}\n"
        f"⭐ Level {guild['level']} | 👥 {member_count}/{guild['max_members']}\n"
        f"⚡ Power: {total_power:,} | 🏆 {guild['wins']}W/{guild['losses']}L\n"
        f"\nID Guild: <code>{guild['id']}</code>\n"
        f"Invite: <code>/joinguild {guild['id']}</code>"
    )
    kb = guild_kb(guild, cb.from_user.id, is_leader)
    if guild.get("photo_id"):
        await cb.message.answer_photo(guild["photo_id"], caption=text, reply_markup=kb)
        await cb.message.delete()
    else:
        await cb.message.edit_text(text, reply_markup=kb)

@router.callback_query(F.data.startswith("guild_kick_menu_"))
async def cb_kick_menu(cb: CallbackQuery):
    guild_id = int(cb.data.split("_")[3])
    guild = await db.fetchone("SELECT * FROM guilds WHERE id=$1", guild_id)
    if guild["leader_id"] != cb.from_user.id:
        await cb.answer("Hanya leader!", show_alert=True)
        return

    members = await db.fetchall("""
        SELECT h.name, h.user_id FROM heroes h
        WHERE h.guild_id=$1 AND h.user_id != $2
    """, guild_id, cb.from_user.id)

    kb = InlineKeyboardBuilder()
    for m in members:
        kb.button(text=f"Kick {m['name']}", callback_data=f"kick_member_{m['user_id']}_{guild_id}")
    kb.button(text="🔙 Kembali", callback_data=f"guild_info_{guild_id}")
    kb.adjust(1)
    await cb.message.edit_text("🚪 Pilih member untuk di-kick:", reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("kick_member_"))
async def cb_kick_member(cb: CallbackQuery):
    parts = cb.data.split("_")
    target_id = int(parts[2])
    guild_id = int(parts[3])
    guild = await db.fetchone("SELECT * FROM guilds WHERE id=$1", guild_id)
    if guild["leader_id"] != cb.from_user.id:
        await cb.answer("Hanya leader!", show_alert=True)
        return
    target = await db.fetchone("SELECT name FROM heroes WHERE user_id=$1", target_id)
    await db.execute("UPDATE heroes SET guild_id=NULL WHERE user_id=$1", target_id)
    try:
        await cb.bot.send_message(target_id, f"⚠️ Kamu telah di-kick dari guild <b>{guild['name']}</b>.")
    except Exception:
        pass
    await cb.answer(f"✅ {target['name']} di-kick!")
    cb.data = f"guild_info_{guild_id}"
    await cb_guild_info(cb)
