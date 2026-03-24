from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from services import database as db
from utils.helpers import CLASS_EMOJI, RARITY_EMOJI, get_battle_power, exp_to_next

router = Router()

def hero_kb(user_id):
    kb = InlineKeyboardBuilder()
    kb.button(text="⚔️ Equip Senjata", callback_data=f"equip_weapon_{user_id}")
    kb.button(text="🎒 Inventory", callback_data=f"inventory_{user_id}")
    kb.button(text="🌳 Talent", callback_data=f"talent_{user_id}")
    kb.button(text="🔗 Referral Link", callback_data=f"referral_{user_id}")
    kb.adjust(2, 2)
    return kb.as_markup()

async def build_hero_text(hero, user_id):
    bp = get_battle_power(hero)
    enl = exp_to_next(hero["level"])
    weapon = await db.fetchone("""
        SELECT w.name, w.rarity, w.atk_bonus FROM weapons w
        JOIN hero_weapons hw ON hw.weapon_id=w.id
        WHERE hw.user_id=$1 AND hw.equipped=TRUE
    """, user_id)

    item_def = await db.fetchval("""
        SELECT COALESCE(SUM(i.def_bonus),0) FROM items i
        JOIN hero_items hi ON hi.item_id=i.id
        WHERE hi.user_id=$1 AND hi.equipped=TRUE
    """, user_id) or 0

    marriage = await db.fetchone("""
        SELECT u.full_name FROM marriages m
        JOIN users u ON (m.user_a=$1 AND u.id=m.user_b) OR (m.user_b=$1 AND u.id=m.user_a)
        WHERE (m.user_a=$1 OR m.user_b=$1) LIMIT 1
    """, user_id)

    total_atk = hero["atk"] + (weapon["atk_bonus"] if weapon else 0)
    total_def = hero["def"] + item_def

    lines = [
        f"{'─'*24}",
        f"{'🔮' if hero['hero_class']=='mage' else CLASS_EMOJI.get(hero['hero_class'],'')} <b>{hero['name']}</b>",
        f"🏅 <i>{hero.get('title','Petualang Baru')}</i>",
        f"{'─'*24}",
        f"📊 Level: <b>{hero['level']}</b>  |  ⚡ BP: <b>{bp:,}</b>",
        f"📈 EXP: {hero['exp']}/{enl}",
        f"{'─'*24}",
        f"❤️ HP: <b>{hero['hp']}/{hero['max_hp']}</b>",
        f"⚔️ ATK: <b>{total_atk}</b>  |  🛡️ DEF: <b>{total_def}</b>  |  💨 SPD: <b>{hero['spd']}</b>",
        f"{'─'*24}",
        f"💰 Gold: <b>{hero['gold']:,}</b>  |  💎 Gems: <b>{hero['gems']}</b>",
        f"🏆 W/L: {hero['wins']}/{hero['losses']}",
    ]
    if weapon:
        lines.append(f"{'─'*24}")
        lines.append(f"🗡️ Senjata: {RARITY_EMOJI.get(weapon['rarity'],'')} {weapon['name']} (+{weapon['atk_bonus']} ATK)")
    if marriage:
        lines.append(f"{'─'*24}")
        lines.append(f"💑 Menikah dengan: <b>{marriage['full_name']}</b>")
    lines.append(f"{'─'*24}")
    return "\n".join(lines)

@router.message(Command("hero", "profil", "profile", "me"))
async def cmd_hero(msg: Message):
    hero = await db.fetchone("SELECT * FROM heroes WHERE user_id=$1", msg.from_user.id)
    if not hero:
        await msg.answer("❌ Kamu belum punya hero! Ketik /start")
        return

    text = await build_hero_text(hero, msg.from_user.id)
    if hero.get("photo_id"):
        await msg.answer_photo(hero["photo_id"], caption=text, reply_markup=hero_kb(msg.from_user.id))
    else:
        await msg.answer(text, reply_markup=hero_kb(msg.from_user.id))

@router.callback_query(F.data.startswith("inventory_"))
async def cb_inventory(cb: CallbackQuery):
    user_id = int(cb.data.split("_")[1])
    if cb.from_user.id != user_id:
        await cb.answer("Ini bukan heromu!", show_alert=True)
        return

    items = await db.fetchall("""
        SELECT i.name, i.item_type, i.rarity, hi.quantity, hi.equipped, hi.id as slot_id
        FROM items i JOIN hero_items hi ON hi.item_id=i.id
        WHERE hi.user_id=$1
    """, user_id)

    if not items:
        await cb.answer("Inventory kosong!", show_alert=True)
        return

    lines = ["🎒 <b>Inventory</b>\n"]
    kb = InlineKeyboardBuilder()
    for it in items:
        eq = "✅" if it["equipped"] else "⬜"
        lines.append(f"{eq} {RARITY_EMOJI.get(it['rarity'],'')} {it['name']} x{it['quantity']}")
        if not it["equipped"]:
            kb.button(text=f"Equip {it['name']}", callback_data=f"equip_item_{it['slot_id']}")
        else:
            kb.button(text=f"Unequip {it['name']}", callback_data=f"unequip_item_{it['slot_id']}")
    kb.button(text="🔙 Kembali", callback_data=f"back_hero_{user_id}")
    kb.adjust(1)
    await cb.message.edit_text("\n".join(lines), reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("equip_item_"))
async def cb_equip_item(cb: CallbackQuery):
    slot_id = int(cb.data.split("_")[2])
    row = await db.fetchone("SELECT * FROM hero_items WHERE id=$1", slot_id)
    if not row or row["user_id"] != cb.from_user.id:
        await cb.answer("Item tidak ditemukan!", show_alert=True)
        return
    await db.execute("UPDATE hero_items SET equipped=TRUE WHERE id=$1", slot_id)
    await cb.answer("✅ Item diequip!")
    await cb_inventory(cb)

@router.callback_query(F.data.startswith("unequip_item_"))
async def cb_unequip_item(cb: CallbackQuery):
    slot_id = int(cb.data.split("_")[2])
    row = await db.fetchone("SELECT * FROM hero_items WHERE id=$1", slot_id)
    if not row or row["user_id"] != cb.from_user.id:
        await cb.answer("Item tidak ditemukan!", show_alert=True)
        return
    await db.execute("UPDATE hero_items SET equipped=FALSE WHERE id=$1", slot_id)
    await cb.answer("✅ Item diunequip!")
    await cb_inventory(cb)

@router.callback_query(F.data.startswith("equip_weapon_"))
async def cb_equip_weapon(cb: CallbackQuery):
    user_id = int(cb.data.split("_")[2])
    if cb.from_user.id != user_id:
        await cb.answer("Bukan heromu!", show_alert=True)
        return

    weapons = await db.fetchall("""
        SELECT w.id, w.name, w.rarity, w.atk_bonus, hw.equipped, hw.id as slot_id
        FROM weapons w JOIN hero_weapons hw ON hw.weapon_id=w.id
        WHERE hw.user_id=$1
    """, user_id)

    if not weapons:
        await cb.answer("Kamu tidak punya senjata! Beli di /shop", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    lines = ["🗡️ <b>Pilih Senjata</b>\n"]
    for w in weapons:
        eq = "✅" if w["equipped"] else "⬜"
        lines.append(f"{eq} {RARITY_EMOJI.get(w['rarity'],'')} {w['name']} (+{w['atk_bonus']} ATK)")
        kb.button(text=f"{'Unequip' if w['equipped'] else 'Equip'} {w['name']}", callback_data=f"toggle_weapon_{w['slot_id']}_{user_id}")
    kb.button(text="🔙 Kembali", callback_data=f"back_hero_{user_id}")
    kb.adjust(1)
    await cb.message.edit_text("\n".join(lines), reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("toggle_weapon_"))
async def cb_toggle_weapon(cb: CallbackQuery):
    parts = cb.data.split("_")
    slot_id = int(parts[2])
    user_id = int(parts[3])
    if cb.from_user.id != user_id:
        await cb.answer("Bukan heromu!", show_alert=True)
        return

    current = await db.fetchval("SELECT equipped FROM hero_weapons WHERE id=$1", slot_id)
    if not current:
        # Unequip semua senjata lain dulu
        await db.execute("UPDATE hero_weapons SET equipped=FALSE WHERE user_id=$1", user_id)
    await db.execute("UPDATE hero_weapons SET equipped=$1 WHERE id=$2", not current, slot_id)
    await cb.answer("✅ Senjata diupdate!")
    # Rebuild weapon panel
    cb.data = f"equip_weapon_{user_id}"
    await cb_equip_weapon(cb)

@router.callback_query(F.data.startswith("talent_"))
async def cb_talent(cb: CallbackQuery):
    user_id = int(cb.data.split("_")[1])
    if cb.from_user.id != user_id:
        await cb.answer("Bukan heromu!", show_alert=True)
        return

    hero = await db.fetchone("SELECT * FROM heroes WHERE user_id=$1", user_id)
    if not hero:
        await cb.answer("Hero tidak ditemukan!", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    lines = [
        f"🌳 <b>Talent Tree</b>",
        f"Poin Tersedia: <b>{hero['talent_points']}</b>",
        f"Path aktif: <b>{hero['talent_path'].capitalize()}</b>\n",
    ]

    if hero["talent_points"] > 0:
        if hero["hero_class"] == "warrior":
            kb.button(text="🗡️ Berserker (+ATK)", callback_data=f"talent_pick_berserker_{user_id}")
            kb.button(text="🛡️ Paladin (+DEF+HP)", callback_data=f"talent_pick_paladin_{user_id}")
        elif hero["hero_class"] == "mage":
            kb.button(text="🔥 Pyromancer (+ATK)", callback_data=f"talent_pick_pyromancer_{user_id}")
            kb.button(text="❄️ Frostmage (+SPD+DEF)", callback_data=f"talent_pick_frostmage_{user_id}")
        elif hero["hero_class"] == "archer":
            kb.button(text="💨 Windwalker (+SPD)", callback_data=f"talent_pick_windwalker_{user_id}")
            kb.button(text="🎯 Deadeye (+ATK kritis)", callback_data=f"talent_pick_deadeye_{user_id}")
        lines.append("Pilih talent untuk diambil:")
    else:
        lines.append("Kamu tidak memiliki poin talent.\nDapatkan poin setiap 5 level naik!")

    kb.button(text="🔙 Kembali", callback_data=f"back_hero_{user_id}")
    kb.adjust(2, 1)
    await cb.message.edit_text("\n".join(lines), reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("talent_pick_"))
async def cb_talent_pick(cb: CallbackQuery):
    parts = cb.data.split("_")
    path = parts[2]
    user_id = int(parts[3])
    if cb.from_user.id != user_id:
        await cb.answer("Bukan heromu!", show_alert=True)
        return

    hero = await db.fetchone("SELECT * FROM heroes WHERE user_id=$1", user_id)
    if hero["talent_points"] <= 0:
        await cb.answer("Tidak ada poin talent!", show_alert=True)
        return

    bonuses = {
        "berserker":   {"atk": 8, "def": 0, "hp": 0, "spd": 0},
        "paladin":     {"atk": 0, "def": 5, "hp": 30, "spd": 0},
        "pyromancer":  {"atk": 10, "def": 0, "hp": 0, "spd": 0},
        "frostmage":   {"atk": 0, "def": 4, "hp": 0, "spd": 5},
        "windwalker":  {"atk": 0, "def": 0, "hp": 0, "spd": 10},
        "deadeye":     {"atk": 7, "def": 0, "hp": 0, "spd": 3},
    }
    b = bonuses.get(path, {})
    await db.execute("""
        UPDATE heroes SET
            talent_points=talent_points-1,
            talent_path=$1,
            atk=atk+$2, def=def+$3, hp=hp+$4, max_hp=max_hp+$4, spd=spd+$5
        WHERE user_id=$6
    """, path, b["atk"], b["def"], b["hp"], b["spd"], user_id)
    await cb.answer(f"✅ Talent {path.capitalize()} dipilih!")
    cb.data = f"talent_{user_id}"
    await cb_talent(cb)

@router.callback_query(F.data.startswith("back_hero_"))
async def cb_back_hero(cb: CallbackQuery):
    user_id = int(cb.data.split("_")[2])
    hero = await db.fetchone("SELECT * FROM heroes WHERE user_id=$1", user_id)
    if not hero:
        await cb.answer("Hero tidak ditemukan!")
        return
    text = await build_hero_text(hero, user_id)
    if hero.get("photo_id"):
        await cb.message.answer_photo(hero["photo_id"], caption=text, reply_markup=hero_kb(user_id))
        await cb.message.delete()
    else:
        await cb.message.edit_text(text, reply_markup=hero_kb(user_id))

@router.callback_query(F.data.startswith("referral_"))
async def cb_referral(cb: CallbackQuery):
    user_id = int(cb.data.split("_")[1])
    user = await db.fetchone("SELECT referral_count FROM users WHERE id=$1", user_id)
    count = user["referral_count"] if user else 0
    bot_info = await cb.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=REF{user_id}"
    await cb.message.edit_text(
        f"🔗 <b>Referral Kamu</b>\n\n"
        f"Link: <code>{link}</code>\n"
        f"Total referral: <b>{count}</b>\n\n"
        f"Setiap teman yang daftar lewat linkmu:\n"
        f"• Kamu dapat +500 gold\n"
        f"• Temanmu dapat +500 gold",
        reply_markup=InlineKeyboardBuilder().button(text="🔙 Kembali", callback_data=f"back_hero_{user_id}").as_markup()
    )
