import os
import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, PhotoSize
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from services import database as db
from utils.helpers import log_admin_action, send_to_log_channel, is_admin

router = Router()

ADMIN_IDS = set(map(int, filter(None, os.getenv("ADMIN_IDS", "").split(","))))

def admin_only(func):
    async def wrapper(msg: Message, *args, **kwargs):
        if not is_admin(msg.from_user.id):
            await msg.answer("❌ Akses ditolak. Command ini hanya untuk admin.")
            return
        return await func(msg, *args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

class AdminState(StatesGroup):
    waiting_broadcast = State()
    waiting_setphoto_type = State()
    waiting_setphoto_id = State()
    waiting_setphoto_photo = State()
    waiting_boss_name = State()
    waiting_boss_hp = State()
    waiting_event_msg = State()

# ─── ADMIN PANEL ─────────────────────────────────────────────
@router.message(Command("admin"))
async def cmd_admin(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Stats", callback_data="adm_stats")
    kb.button(text="📢 Broadcast", callback_data="adm_broadcast")
    kb.button(text="🖼️ Set Photo", callback_data="adm_setphoto_menu")
    kb.button(text="🔧 Maintenance", callback_data="adm_maintenance")
    kb.button(text="🐉 Spawn Boss", callback_data="adm_spawn_boss")
    kb.button(text="⚡ Double EXP", callback_data="adm_double_exp")
    kb.button(text="💰 Double Gold", callback_data="adm_double_gold")
    kb.button(text="🔍 Cari User", callback_data="adm_find_user")
    kb.button(text="📋 Admin Logs", callback_data="adm_logs")
    kb.button(text="⚔️ Force War", callback_data="adm_force_war")
    kb.adjust(2)
    await msg.answer("🛡️ <b>Admin Panel</b>", reply_markup=kb.as_markup())

# ─── STATS ───────────────────────────────────────────────────
@router.callback_query(F.data == "adm_stats")
async def adm_stats(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    total_users = await db.fetchval("SELECT COUNT(*) FROM users")
    active_today = await db.fetchval("SELECT COUNT(*) FROM users WHERE last_active::date=NOW()::date")
    new_week = await db.fetchval("SELECT COUNT(*) FROM users WHERE created_at > NOW() - INTERVAL '7 days'")
    total_heroes = await db.fetchval("SELECT COUNT(*) FROM heroes")
    total_guilds = await db.fetchval("SELECT COUNT(*) FROM guilds")
    total_wars = await db.fetchval("SELECT COUNT(*) FROM guild_wars WHERE status='ended'")
    total_market = await db.fetchval("SELECT COUNT(*) FROM market_listings WHERE is_sold=FALSE")
    total_marriages = await db.fetchval("SELECT COUNT(*) FROM marriages")
    banned = await db.fetchval("SELECT COUNT(*) FROM users WHERE is_banned=TRUE")
    boss = await db.fetchone("SELECT * FROM world_boss WHERE is_active=TRUE")

    text = (
        f"📊 <b>Game Statistics</b>\n"
        f"{'─'*24}\n"
        f"👤 Total user: <b>{total_users}</b>\n"
        f"🟢 Aktif hari ini: <b>{active_today}</b>\n"
        f"🆕 Baru (7 hari): <b>{new_week}</b>\n"
        f"🚫 Banned: <b>{banned}</b>\n"
        f"{'─'*24}\n"
        f"⚔️ Total hero: <b>{total_heroes}</b>\n"
        f"🏰 Total guild: <b>{total_guilds}</b>\n"
        f"⚔️ Total war selesai: <b>{total_wars}</b>\n"
        f"🏪 Listing market: <b>{total_market}</b>\n"
        f"💑 Pernikahan aktif: <b>{total_marriages}</b>\n"
        f"{'─'*24}\n"
        f"🐉 World boss: {'<b>AKTIF</b> — ' + boss['name'] if boss else 'Tidak aktif'}\n"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Kembali", callback_data="adm_back")
    await cb.message.edit_text(text, reply_markup=kb.as_markup())

# ─── BROADCAST ───────────────────────────────────────────────
@router.callback_query(F.data == "adm_broadcast")
async def adm_broadcast_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id): return
    await cb.message.edit_text("📢 Ketik pesan broadcast (support HTML bold/italic):")
    await state.set_state(AdminState.waiting_broadcast)

@router.message(AdminState.waiting_broadcast)
async def adm_broadcast_send(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id): return
    await state.clear()
    users = await db.fetchall("SELECT id FROM users WHERE is_banned=FALSE")
    sent = failed = 0
    status_msg = await msg.answer(f"📤 Broadcasting ke {len(users)} user...")
    for u in users:
        try:
            await msg.bot.send_message(u["id"], f"📢 <b>Pengumuman Admin</b>\n\n{msg.text}")
            sent += 1
        except Exception:
            failed += 1
        if sent % 50 == 0:
            try:
                await status_msg.edit_text(f"📤 Progress: {sent}/{len(users)}...")
            except Exception:
                pass
        await asyncio.sleep(0.05)
    await status_msg.edit_text(f"✅ Broadcast selesai!\nTerkirim: {sent} | Gagal: {failed}")
    await log_admin_action(msg.from_user.id, "broadcast", "all", f"Sent to {sent} users")
    await send_to_log_channel(msg.bot, f"📢 Admin {msg.from_user.id} broadcast ke {sent} user.")

# ─── SET PHOTO ───────────────────────────────────────────────
@router.callback_query(F.data == "adm_setphoto_menu")
async def adm_setphoto_menu(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    text = (
        "🖼️ <b>Set Photo</b>\n\n"
        "Cara pakai:\n"
        "1. Kirim foto ke bot\n"
        "2. <b>Reply</b> foto tersebut dengan command:\n\n"
        "<code>/setphoto hero</code> — foto hero (user tertentu)\n"
        "<code>/setphoto item [id]</code> — foto item\n"
        "<code>/setphoto weapon [id]</code> — foto senjata\n"
        "<code>/setphoto dungeon [key]</code> — foto dungeon\n"
        "<code>/setphoto guild [id]</code> — foto guild\n"
        "<code>/setphoto boss</code> — foto world boss\n\n"
        "Contoh: reply foto lalu ketik\n"
        "<code>/setphoto item 3</code>"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="📋 List Item", callback_data="adm_list_items")
    kb.button(text="🗡️ List Weapon", callback_data="adm_list_weapons")
    kb.button(text="🏰 List Dungeon", callback_data="adm_list_dungeons")
    kb.button(text="🔙 Kembali", callback_data="adm_back")
    kb.adjust(2, 1)
    await cb.message.edit_text(text, reply_markup=kb.as_markup())

@router.message(Command("setphoto"))
async def cmd_setphoto(msg: Message):
    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Akses ditolak.")
        return

    # Must be a reply to a photo
    if not msg.reply_to_message or not msg.reply_to_message.photo:
        await msg.answer(
            "❌ Kamu harus <b>reply</b> ke sebuah foto!\n\n"
            "Cara:\n1. Kirim foto ke bot\n2. Reply foto itu dengan /setphoto [tipe] [id]"
        )
        return

    photo_id = msg.reply_to_message.photo[-1].file_id
    args = msg.text.split()

    if len(args) < 2:
        await msg.answer("Format: /setphoto [tipe] [id/key]\nContoh: /setphoto item 3")
        return

    photo_type = args[1].lower()

    if photo_type == "hero":
        # Set foto untuk hero pemain yang reply atau disebutkan
        if len(args) >= 3:
            try:
                target_id = int(args[2])
            except ValueError:
                await msg.answer("❌ ID user tidak valid.")
                return
        elif msg.reply_to_message.forward_from:
            target_id = msg.reply_to_message.forward_from.id
        else:
            await msg.answer("Format: /setphoto hero [user_id]")
            return

        hero = await db.fetchone("SELECT * FROM heroes WHERE user_id=$1", target_id)
        if not hero:
            await msg.answer("❌ Hero tidak ditemukan.")
            return
        await db.execute("UPDATE heroes SET photo_id=$1 WHERE user_id=$2", photo_id, target_id)
        await log_admin_action(msg.from_user.id, "setphoto", f"hero:{target_id}", photo_id)
        await msg.answer(f"✅ Foto hero <b>{hero['name']}</b> berhasil diset!")

    elif photo_type == "item":
        if len(args) < 3:
            await msg.answer("Format: /setphoto item [id]")
            return
        try:
            item_id = int(args[2])
        except ValueError:
            await msg.answer("❌ ID item tidak valid.")
            return
        item = await db.fetchone("SELECT name FROM items WHERE id=$1", item_id)
        if not item:
            await msg.answer(f"❌ Item ID {item_id} tidak ditemukan.")
            return
        await db.execute("UPDATE items SET photo_id=$1 WHERE id=$2", photo_id, item_id)
        await log_admin_action(msg.from_user.id, "setphoto", f"item:{item_id}", photo_id)
        await msg.answer(f"✅ Foto item <b>{item['name']}</b> (ID:{item_id}) berhasil diset!")

    elif photo_type == "weapon":
        if len(args) < 3:
            await msg.answer("Format: /setphoto weapon [id]")
            return
        try:
            weapon_id = int(args[2])
        except ValueError:
            await msg.answer("❌ ID senjata tidak valid.")
            return
        weapon = await db.fetchone("SELECT name FROM weapons WHERE id=$1", weapon_id)
        if not weapon:
            await msg.answer(f"❌ Weapon ID {weapon_id} tidak ditemukan.")
            return
        await db.execute("UPDATE weapons SET photo_id=$1 WHERE id=$2", photo_id, weapon_id)
        await log_admin_action(msg.from_user.id, "setphoto", f"weapon:{weapon_id}", photo_id)
        await msg.answer(f"✅ Foto senjata <b>{weapon['name']}</b> (ID:{weapon_id}) berhasil diset!")

    elif photo_type == "dungeon":
        if len(args) < 3:
            await msg.answer("Format: /setphoto dungeon [key]\nKey: forest, cave, volcano, abyss, dragon")
            return
        dkey = args[2].lower()
        dungeon = await db.fetchone("SELECT name FROM dungeons WHERE key=$1", dkey)
        if not dungeon:
            await msg.answer(f"❌ Dungeon '{dkey}' tidak ditemukan.")
            return
        await db.execute("UPDATE dungeons SET photo_id=$1 WHERE key=$2", photo_id, dkey)
        await log_admin_action(msg.from_user.id, "setphoto", f"dungeon:{dkey}", photo_id)
        await msg.answer(f"✅ Foto dungeon <b>{dungeon['name']}</b> berhasil diset!")

    elif photo_type == "guild":
        if len(args) < 3:
            await msg.answer("Format: /setphoto guild [guild_id]")
            return
        try:
            guild_id = int(args[2])
        except ValueError:
            await msg.answer("❌ ID guild tidak valid.")
            return
        guild = await db.fetchone("SELECT name FROM guilds WHERE id=$1", guild_id)
        if not guild:
            await msg.answer(f"❌ Guild ID {guild_id} tidak ditemukan.")
            return
        await db.execute("UPDATE guilds SET photo_id=$1 WHERE id=$2", photo_id, guild_id)
        await log_admin_action(msg.from_user.id, "setphoto", f"guild:{guild_id}", photo_id)
        await msg.answer(f"✅ Foto guild <b>{guild['name']}</b> berhasil diset!")

    elif photo_type == "boss":
        boss = await db.fetchone("SELECT * FROM world_boss WHERE is_active=TRUE")
        if not boss:
            # Set foto untuk boss terbaru
            await db.execute("UPDATE world_boss SET photo_id=$1 WHERE id=(SELECT MAX(id) FROM world_boss)", photo_id)
        else:
            await db.execute("UPDATE world_boss SET photo_id=$1 WHERE id=$2", photo_id, boss["id"])
        await log_admin_action(msg.from_user.id, "setphoto", "boss", photo_id)
        await msg.answer("✅ Foto world boss berhasil diset!")

    else:
        await msg.answer(
            "❌ Tipe tidak valid.\nTipe tersedia: hero, item, weapon, dungeon, guild, boss"
        )

# ─── LIST HELPERS ────────────────────────────────────────────
@router.callback_query(F.data == "adm_list_items")
async def adm_list_items(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    items = await db.fetchall("SELECT id, name, rarity FROM items ORDER BY id")
    lines = ["📋 <b>Daftar Item</b>\n"]
    for it in items:
        has_photo = "🖼️" if await db.fetchval("SELECT photo_id FROM items WHERE id=$1", it["id"]) else "⬜"
        lines.append(f"{has_photo} ID:<b>{it['id']}</b> — {it['name']} ({it['rarity']})")
    lines.append("\nGunakan: /setphoto item [id]")
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Kembali", callback_data="adm_setphoto_menu")
    await cb.message.edit_text("\n".join(lines), reply_markup=kb.as_markup())

@router.callback_query(F.data == "adm_list_weapons")
async def adm_list_weapons(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    weapons = await db.fetchall("SELECT id, name, rarity FROM weapons ORDER BY id")
    lines = ["🗡️ <b>Daftar Senjata</b>\n"]
    for w in weapons:
        has_photo = "🖼️" if await db.fetchval("SELECT photo_id FROM weapons WHERE id=$1", w["id"]) else "⬜"
        lines.append(f"{has_photo} ID:<b>{w['id']}</b> — {w['name']} ({w['rarity']})")
    lines.append("\nGunakan: /setphoto weapon [id]")
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Kembali", callback_data="adm_setphoto_menu")
    await cb.message.edit_text("\n".join(lines), reply_markup=kb.as_markup())

@router.callback_query(F.data == "adm_list_dungeons")
async def adm_list_dungeons(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    dungeons = await db.fetchall("SELECT key, name FROM dungeons ORDER BY id")
    lines = ["🏰 <b>Daftar Dungeon</b>\n"]
    for d in dungeons:
        has_photo = "🖼️" if await db.fetchval("SELECT photo_id FROM dungeons WHERE key=$1", d["key"]) else "⬜"
        lines.append(f"{has_photo} Key:<b>{d['key']}</b> — {d['name']}")
    lines.append("\nGunakan: /setphoto dungeon [key]")
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Kembali", callback_data="adm_setphoto_menu")
    await cb.message.edit_text("\n".join(lines), reply_markup=kb.as_markup())

# ─── MAINTENANCE ─────────────────────────────────────────────
@router.callback_query(F.data == "adm_maintenance")
async def adm_maintenance(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    current = await db.fetchval("SELECT value FROM settings WHERE key='maintenance'")
    new_val = "false" if current == "true" else "true"
    await db.execute("UPDATE settings SET value=$1 WHERE key='maintenance'", new_val)
    status = "🔴 ON" if new_val == "true" else "🟢 OFF"
    await cb.answer(f"Maintenance {status}", show_alert=True)
    await log_admin_action(cb.from_user.id, "maintenance", "system", new_val)
    await send_to_log_channel(cb.bot, f"🔧 Admin {cb.from_user.id} set maintenance={new_val}")
    await adm_back(cb)

# ─── SPAWN WORLD BOSS ─────────────────────────────────────────
@router.callback_query(F.data == "adm_spawn_boss")
async def adm_spawn_boss_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id): return
    existing = await db.fetchone("SELECT id FROM world_boss WHERE is_active=TRUE")
    if existing:
        kb = InlineKeyboardBuilder()
        kb.button(text="☠️ Kill Boss Sekarang", callback_data="adm_kill_boss")
        kb.button(text="🔙 Kembali", callback_data="adm_back")
        kb.adjust(1)
        await cb.message.edit_text("⚠️ World boss sudah aktif!", reply_markup=kb.as_markup())
        return
    await cb.message.edit_text("🐉 Masukkan nama world boss:")
    await state.set_state(AdminState.waiting_boss_name)

@router.message(AdminState.waiting_boss_name)
async def adm_boss_name(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id): return
    await state.update_data(boss_name=msg.text.strip())
    await msg.answer("💪 Masukkan HP boss (contoh: 1000000):")
    await state.set_state(AdminState.waiting_boss_hp)

@router.message(AdminState.waiting_boss_hp)
async def adm_boss_hp(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id): return
    try:
        hp = int(msg.text.strip())
        if hp < 1000:
            await msg.answer("❌ HP minimal 1000.")
            return
    except ValueError:
        await msg.answer("❌ Masukkan angka.")
        return

    data = await state.get_data()
    name = data["boss_name"]
    await state.clear()

    await db.execute("""
        INSERT INTO world_boss (name, max_hp, current_hp, is_active, started_at)
        VALUES ($1, $2, $2, TRUE, NOW())
    """, name, hp)

    # Broadcast ke semua user
    users = await db.fetchall("SELECT id FROM users WHERE is_banned=FALSE")
    sent = 0
    for u in users:
        try:
            await msg.bot.send_message(u["id"],
                f"🐉 <b>WORLD BOSS MUNCUL!</b>\n\n"
                f"<b>{name}</b> sedang mengamuk!\n"
                f"HP: {hp:,}\n\n"
                f"Gunakan /boss untuk menyerang! 🗡️"
            )
            sent += 1
        except Exception:
            pass
        await asyncio.sleep(0.05)

    await msg.answer(f"✅ World boss <b>{name}</b> di-spawn! Notif ke {sent} user.")
    await log_admin_action(msg.from_user.id, "spawn_boss", name, f"HP:{hp}")

@router.callback_query(F.data == "adm_kill_boss")
async def adm_kill_boss(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    await db.execute("UPDATE world_boss SET is_active=FALSE, ended_at=NOW() WHERE is_active=TRUE")
    await cb.answer("✅ Boss dihapus.", show_alert=True)
    await adm_back(cb)

# ─── DOUBLE EXP / GOLD ───────────────────────────────────────
@router.callback_query(F.data == "adm_double_exp")
async def adm_double_exp(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    current = await db.fetchval("SELECT value FROM settings WHERE key='double_exp'")
    new_val = "false" if current == "true" else "true"
    await db.execute("UPDATE settings SET value=$1 WHERE key='double_exp'", new_val)
    status = "🟢 ON" if new_val == "true" else "🔴 OFF"
    await cb.answer(f"Double EXP {status}", show_alert=True)
    if new_val == "true":
        users = await db.fetchall("SELECT id FROM users WHERE is_banned=FALSE")
        for u in users:
            try:
                await cb.bot.send_message(u["id"], "⭐ <b>EVENT: Double EXP aktif!</b>\nSemua EXP x2 sekarang!")
            except Exception:
                pass
            await asyncio.sleep(0.05)
    await adm_back(cb)

@router.callback_query(F.data == "adm_double_gold")
async def adm_double_gold(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    current = await db.fetchval("SELECT value FROM settings WHERE key='double_gold'")
    new_val = "false" if current == "true" else "true"
    await db.execute("UPDATE settings SET value=$1 WHERE key='double_gold'", new_val)
    status = "🟢 ON" if new_val == "true" else "🔴 OFF"
    await cb.answer(f"Double Gold {status}", show_alert=True)
    if new_val == "true":
        users = await db.fetchall("SELECT id FROM users WHERE is_banned=FALSE")
        for u in users:
            try:
                await cb.bot.send_message(u["id"], "💰 <b>EVENT: Double Gold aktif!</b>\nSemua Gold x2 sekarang!")
            except Exception:
                pass
            await asyncio.sleep(0.05)
    await adm_back(cb)

# ─── BAN / UNBAN ─────────────────────────────────────────────
@router.message(Command("ban"))
async def cmd_ban(msg: Message):
    if not is_admin(msg.from_user.id): return
    args = msg.text.split(maxsplit=2)
    if len(args) < 2:
        await msg.answer("Format: /ban [user_id] [alasan]")
        return
    try:
        uid = int(args[1])
    except ValueError:
        await msg.answer("❌ ID tidak valid.")
        return
    reason = args[2] if len(args) > 2 else "Melanggar aturan"
    user = await db.fetchone("SELECT * FROM users WHERE id=$1", uid)
    if not user:
        await msg.answer("❌ User tidak ditemukan.")
        return
    await db.execute("UPDATE users SET is_banned=TRUE, ban_reason=$1 WHERE id=$2", reason, uid)
    await log_admin_action(msg.from_user.id, "ban", str(uid), reason)
    await send_to_log_channel(msg.bot, f"🚫 Admin {msg.from_user.id} banned user {uid}. Alasan: {reason}")
    try:
        await msg.bot.send_message(uid, f"🚫 Akun kamu telah dibanned.\nAlasan: {reason}")
    except Exception:
        pass
    await msg.answer(f"✅ User {uid} ({user['full_name']}) dibanned.\nAlasan: {reason}")

@router.message(Command("unban"))
async def cmd_unban(msg: Message):
    if not is_admin(msg.from_user.id): return
    args = msg.text.split()
    if len(args) < 2:
        await msg.answer("Format: /unban [user_id]")
        return
    try:
        uid = int(args[1])
    except ValueError:
        await msg.answer("❌ ID tidak valid.")
        return
    await db.execute("UPDATE users SET is_banned=FALSE, ban_reason=NULL WHERE id=$1", uid)
    await log_admin_action(msg.from_user.id, "unban", str(uid), "")
    try:
        await msg.bot.send_message(uid, "✅ Akun kamu telah di-unban. Selamat bermain!")
    except Exception:
        pass
    await msg.answer(f"✅ User {uid} di-unban.")

# ─── GIVE / TAKE ─────────────────────────────────────────────
@router.message(Command("give"))
async def cmd_give(msg: Message):
    if not is_admin(msg.from_user.id): return
    # /give [user_id] [gold/exp/gems/level] [amount]
    args = msg.text.split()
    if len(args) < 4:
        await msg.answer("Format: /give [user_id] [gold|exp|gems|level] [jumlah]")
        return
    try:
        uid = int(args[1])
        field = args[2].lower()
        amount = int(args[3])
    except ValueError:
        await msg.answer("❌ Format tidak valid.")
        return
    if field not in ("gold", "exp", "gems", "level"):
        await msg.answer("❌ Field: gold, exp, gems, level")
        return
    hero = await db.fetchone("SELECT * FROM heroes WHERE user_id=$1", uid)
    if not hero:
        await msg.answer("❌ Hero tidak ditemukan.")
        return
    await db.execute(f"UPDATE heroes SET {field}={field}+$1 WHERE user_id=$2", amount, uid)
    await log_admin_action(msg.from_user.id, "give", str(uid), f"{field}+{amount}")
    try:
        await msg.bot.send_message(uid, f"🎁 Admin memberikan +{amount} {field}!")
    except Exception:
        pass
    await msg.answer(f"✅ +{amount} {field} diberikan ke user {uid}.")

@router.message(Command("take"))
async def cmd_take(msg: Message):
    if not is_admin(msg.from_user.id): return
    args = msg.text.split()
    if len(args) < 4:
        await msg.answer("Format: /take [user_id] [gold|exp|gems] [jumlah]")
        return
    try:
        uid = int(args[1])
        field = args[2].lower()
        amount = int(args[3])
    except ValueError:
        await msg.answer("❌ Format tidak valid.")
        return
    if field not in ("gold", "exp", "gems"):
        await msg.answer("❌ Field: gold, exp, gems")
        return
    await db.execute(f"UPDATE heroes SET {field}=GREATEST({field}-$1,0) WHERE user_id=$2", amount, uid)
    await log_admin_action(msg.from_user.id, "take", str(uid), f"{field}-{amount}")
    await msg.answer(f"✅ -{amount} {field} diambil dari user {uid}.")

# ─── USERINFO ────────────────────────────────────────────────
@router.message(Command("userinfo"))
async def cmd_userinfo(msg: Message):
    if not is_admin(msg.from_user.id): return
    args = msg.text.split()
    if len(args) < 2:
        await msg.answer("Format: /userinfo [user_id]")
        return
    try:
        uid = int(args[1])
    except ValueError:
        await msg.answer("❌ ID tidak valid.")
        return

    user = await db.fetchone("SELECT * FROM users WHERE id=$1", uid)
    hero = await db.fetchone("SELECT * FROM heroes WHERE user_id=$1", uid)
    if not user:
        await msg.answer("❌ User tidak ditemukan.")
        return

    guild = None
    if hero and hero["guild_id"]:
        guild = await db.fetchone("SELECT name FROM guilds WHERE id=$1", hero["guild_id"])

    marriage = None
    if hero:
        marriage = await db.fetchone("""
            SELECT u.full_name FROM marriages m
            JOIN users u ON (m.user_a=$1 AND u.id=m.user_b) OR (m.user_b=$1 AND u.id=m.user_a)
            WHERE m.user_a=$1 OR m.user_b=$1
        """, uid)

    text = (
        f"👤 <b>Info User</b>\n"
        f"{'─'*22}\n"
        f"ID: <code>{user['id']}</code>\n"
        f"Username: @{user['username'] or '-'}\n"
        f"Nama: {user['full_name']}\n"
        f"Daftar: {user['created_at'].strftime('%d/%m/%Y %H:%M')}\n"
        f"Aktif terakhir: {user['last_active'].strftime('%d/%m/%Y %H:%M')}\n"
        f"Referral: {user['referral_count']} orang\n"
        f"Status: {'🚫 BANNED' if user['is_banned'] else '✅ Aktif'}\n"
    )
    if user["is_banned"]:
        text += f"Alasan ban: {user['ban_reason']}\n"
    if hero:
        text += (
            f"{'─'*22}\n"
            f"Hero: <b>{hero['name']}</b> Lv.{hero['level']} ({hero['hero_class']})\n"
            f"💰 Gold: {hero['gold']:,} | 💎 Gems: {hero['gems']}\n"
            f"⚔️ W/L: {hero['wins']}/{hero['losses']}\n"
            f"🏰 Dungeon: {hero['dungeons_done']} runs\n"
        )
    if guild:
        text += f"Guild: {guild['name']}\n"
    if marriage:
        text += f"Menikah dengan: {marriage['full_name']}\n"

    kb = InlineKeyboardBuilder()
    if user["is_banned"]:
        kb.button(text="✅ Unban", callback_data=f"quick_unban_{uid}")
    else:
        kb.button(text="🚫 Ban", callback_data=f"quick_ban_{uid}")
    kb.button(text="🎁 Beri Gold", callback_data=f"quick_give_gold_{uid}")
    kb.button(text="🔄 Reset CD", callback_data=f"quick_resetcd_{uid}")
    kb.adjust(2)
    await msg.answer(text, reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("quick_unban_"))
async def quick_unban(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    uid = int(cb.data.split("_")[2])
    await db.execute("UPDATE users SET is_banned=FALSE, ban_reason=NULL WHERE id=$1", uid)
    await cb.answer("✅ User di-unban!")

@router.callback_query(F.data.startswith("quick_ban_"))
async def quick_ban(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    uid = int(cb.data.split("_")[2])
    await db.execute("UPDATE users SET is_banned=TRUE, ban_reason='Admin action' WHERE id=$1", uid)
    await cb.answer("✅ User dibanned!")

@router.callback_query(F.data.startswith("quick_give_gold_"))
async def quick_give_gold(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    uid = int(cb.data.split("_")[3])
    await db.execute("UPDATE heroes SET gold=gold+1000 WHERE user_id=$1", uid)
    try:
        await cb.bot.send_message(uid, "🎁 Admin memberikan +1000 gold!")
    except Exception:
        pass
    await cb.answer("✅ +1000 gold diberikan!")

@router.callback_query(F.data.startswith("quick_resetcd_"))
async def quick_resetcd(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    uid = int(cb.data.split("_")[2])
    await db.execute("DELETE FROM cooldowns WHERE user_id=$1", uid)
    try:
        await cb.bot.send_message(uid, "🔄 Semua cooldown kamu telah direset oleh admin!")
    except Exception:
        pass
    await cb.answer("✅ Cooldown direset!")

# ─── RESET COOLDOWN ──────────────────────────────────────────
@router.message(Command("resetcd"))
async def cmd_resetcd(msg: Message):
    if not is_admin(msg.from_user.id): return
    args = msg.text.split()
    if len(args) < 2:
        await msg.answer("Format: /resetcd [user_id]")
        return
    try:
        uid = int(args[1])
    except ValueError:
        await msg.answer("❌ ID tidak valid.")
        return
    await db.execute("DELETE FROM cooldowns WHERE user_id=$1", uid)
    await log_admin_action(msg.from_user.id, "resetcd", str(uid), "")
    try:
        await msg.bot.send_message(uid, "🔄 Cooldown kamu direset oleh admin!")
    except Exception:
        pass
    await msg.answer(f"✅ Cooldown user {uid} direset.")

# ─── FORCE WAR ───────────────────────────────────────────────
@router.callback_query(F.data == "adm_force_war")
async def adm_force_war_menu(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    guilds = await db.fetchall("SELECT id, name FROM guilds ORDER BY id")
    lines = ["⚔️ <b>Force Guild War</b>\n\nGunakan command:\n<code>/forcewar [guild_a_id] [guild_b_id]</code>\n\nDaftar Guild:"]
    for g in guilds:
        lines.append(f"ID:{g['id']} — {g['name']}")
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Kembali", callback_data="adm_back")
    await cb.message.edit_text("\n".join(lines), reply_markup=kb.as_markup())

@router.message(Command("forcewar"))
async def cmd_force_war(msg: Message):
    if not is_admin(msg.from_user.id): return
    args = msg.text.split()
    if len(args) < 3:
        await msg.answer("Format: /forcewar [guild_a_id] [guild_b_id]")
        return
    try:
        ga = int(args[1])
        gb = int(args[2])
    except ValueError:
        await msg.answer("❌ ID tidak valid.")
        return

    guild_a = await db.fetchone("SELECT * FROM guilds WHERE id=$1", ga)
    guild_b = await db.fetchone("SELECT * FROM guilds WHERE id=$1", gb)
    if not guild_a or not guild_b:
        await msg.answer("❌ Salah satu guild tidak ditemukan.")
        return

    await db.execute("""
        INSERT INTO guild_wars (guild_a, guild_b, status)
        VALUES ($1, $2, 'active')
    """, ga, gb)

    await log_admin_action(msg.from_user.id, "force_war", f"{ga}vs{gb}", "")
    await msg.answer(f"✅ War antara <b>{guild_a['name']}</b> VS <b>{guild_b['name']}</b> dimulai!")

    for gid in [ga, gb]:
        other = guild_b if gid == ga else guild_a
        members = await db.fetchall("SELECT user_id FROM heroes WHERE guild_id=$1", gid)
        for m in members:
            try:
                await msg.bot.send_message(m["user_id"],
                    f"⚔️ <b>Guild War dimulai!</b>\nVS <b>{other['name']}</b>!")
            except Exception:
                pass

# ─── ADMIN LOGS ──────────────────────────────────────────────
@router.callback_query(F.data == "adm_logs")
async def adm_logs(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    logs = await db.fetchall("""
        SELECT * FROM admin_logs ORDER BY created_at DESC LIMIT 15
    """)
    lines = ["📋 <b>Admin Logs (15 terbaru)</b>\n"]
    for l in logs:
        lines.append(
            f"[{l['created_at'].strftime('%d/%m %H:%M')}] "
            f"Admin:{l['admin_id']} | {l['action']} → {l['target']}"
        )
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Kembali", callback_data="adm_back")
    await cb.message.edit_text("\n".join(lines) or "Tidak ada log.", reply_markup=kb.as_markup())

# ─── FIND USER ───────────────────────────────────────────────
@router.callback_query(F.data == "adm_find_user")
async def adm_find_user_hint(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Kembali", callback_data="adm_back")
    await cb.message.edit_text(
        "🔍 <b>Cari User</b>\n\nGunakan: /userinfo [user_id]\n\nContoh: /userinfo 123456789",
        reply_markup=kb.as_markup()
    )

# ─── BACK ────────────────────────────────────────────────────
@router.callback_query(F.data == "adm_back")
async def adm_back(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Stats", callback_data="adm_stats")
    kb.button(text="📢 Broadcast", callback_data="adm_broadcast")
    kb.button(text="🖼️ Set Photo", callback_data="adm_setphoto_menu")
    kb.button(text="🔧 Maintenance", callback_data="adm_maintenance")
    kb.button(text="🐉 Spawn Boss", callback_data="adm_spawn_boss")
    kb.button(text="⚡ Double EXP", callback_data="adm_double_exp")
    kb.button(text="💰 Double Gold", callback_data="adm_double_gold")
    kb.button(text="🔍 Cari User", callback_data="adm_find_user")
    kb.button(text="📋 Admin Logs", callback_data="adm_logs")
    kb.button(text="⚔️ Force War", callback_data="adm_force_war")
    kb.adjust(2)
    await cb.message.edit_text("🛡️ <b>Admin Panel</b>", reply_markup=kb.as_markup())

# ─── BANLIST ─────────────────────────────────────────────────
@router.message(Command("banlist"))
async def cmd_banlist(msg: Message):
    if not is_admin(msg.from_user.id): return
    banned = await db.fetchall("SELECT id, username, full_name, ban_reason FROM users WHERE is_banned=TRUE LIMIT 20")
    if not banned:
        await msg.answer("✅ Tidak ada user yang dibanned.")
        return
    lines = [f"🚫 <b>Daftar Banned ({len(banned)} user)</b>\n"]
    for u in banned:
        lines.append(f"• <code>{u['id']}</code> @{u['username'] or '-'} — {u['ban_reason'] or '-'}")
    await msg.answer("\n".join(lines))

# ─── HELP ADMIN ──────────────────────────────────────────────
@router.message(Command("adminhelp"))
async def cmd_adminhelp(msg: Message):
    if not is_admin(msg.from_user.id): return
    await msg.answer(
        "🛡️ <b>Daftar Command Admin</b>\n"
        "{'─'*24}\n"
        "/admin — Panel admin utama\n"
        "/ban [id] [alasan] — Ban user\n"
        "/unban [id] — Unban user\n"
        "/banlist — Daftar banned\n"
        "/give [id] [field] [jumlah] — Beri resource\n"
        "/take [id] [field] [jumlah] — Ambil resource\n"
        "/userinfo [id] — Info lengkap user\n"
        "/resetcd [id] — Reset cooldown user\n"
        "/forcewar [id_a] [id_b] — Paksa guild war\n\n"
        "🖼️ <b>Set Photo</b> (reply foto + command):\n"
        "/setphoto hero [user_id]\n"
        "/setphoto item [id]\n"
        "/setphoto weapon [id]\n"
        "/setphoto dungeon [key]\n"
        "/setphoto guild [id]\n"
        "/setphoto boss\n\n"
        "Panel lengkap: /admin"
    )
