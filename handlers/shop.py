from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from services import database as db
from utils.helpers import RARITY_EMOJI, check_cooldown, set_cooldown, format_seconds

router = Router()

@router.message(Command("shop", "toko"))
async def cmd_shop(msg: Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="🗡️ Senjata", callback_data="shop_weapons")
    kb.button(text="🎒 Item", callback_data="shop_items")
    kb.adjust(2)
    await msg.answer("🛍️ <b>Toko</b>\nBeli senjata dan item!", reply_markup=kb.as_markup())

@router.callback_query(F.data == "shop_weapons")
async def cb_shop_weapons(cb: CallbackQuery):
    weapons = await db.fetchall("SELECT * FROM weapons WHERE is_available=TRUE ORDER BY price")
    kb = InlineKeyboardBuilder()
    lines = ["🗡️ <b>Toko Senjata</b>\n"]
    for w in weapons:
        lines.append(
            f"{RARITY_EMOJI.get(w['rarity'],'')} <b>{w['name']}</b>\n"
            f"   ⚔️+{w['atk_bonus']} | 💰 {w['price']:,} gold\n"
            f"   {w['description']}"
        )
        kb.button(text=f"Beli {w['name']} ({w['price']:,}g)", callback_data=f"buy_weapon_{w['id']}")
    kb.button(text="🔙 Kembali", callback_data="shop_back")
    kb.adjust(1)
    await cb.message.edit_text("\n".join(lines), reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("buy_weapon_"))
async def cb_buy_weapon(cb: CallbackQuery):
    weapon_id = int(cb.data.split("_")[2])
    weapon = await db.fetchone("SELECT * FROM weapons WHERE id=$1 AND is_available=TRUE", weapon_id)
    hero = await db.fetchone("SELECT * FROM heroes WHERE user_id=$1", cb.from_user.id)
    if not weapon or not hero:
        await cb.answer("Tidak ditemukan!", show_alert=True)
        return
    if hero["gold"] < weapon["price"]:
        await cb.answer(f"Gold tidak cukup! Butuh {weapon['price']:,} gold.", show_alert=True)
        return
    await db.execute("UPDATE heroes SET gold=gold-$1 WHERE user_id=$2", weapon["price"], cb.from_user.id)
    await db.execute("INSERT INTO hero_weapons (user_id, weapon_id) VALUES ($1, $2)", cb.from_user.id, weapon_id)
    await cb.answer(f"✅ {weapon['name']} dibeli! Cek /hero untuk equip.", show_alert=True)

@router.callback_query(F.data == "shop_items")
async def cb_shop_items(cb: CallbackQuery):
    items = await db.fetchall("SELECT * FROM items WHERE is_available=TRUE ORDER BY price")
    kb = InlineKeyboardBuilder()
    lines = ["🎒 <b>Toko Item</b>\n"]
    for it in items:
        bonuses = []
        if it["hp_bonus"]: bonuses.append(f"❤️+{it['hp_bonus']}")
        if it["atk_bonus"]: bonuses.append(f"⚔️+{it['atk_bonus']}")
        if it["def_bonus"]: bonuses.append(f"🛡️+{it['def_bonus']}")
        bonus_str = " ".join(bonuses) or ""
        lines.append(
            f"{RARITY_EMOJI.get(it['rarity'],'')} <b>{it['name']}</b> {bonus_str}\n"
            f"   💰 {it['price']:,} gold — {it['description']}"
        )
        kb.button(text=f"Beli {it['name']} ({it['price']:,}g)", callback_data=f"buy_item_{it['id']}")
    kb.button(text="🔙 Kembali", callback_data="shop_back")
    kb.adjust(1)
    await cb.message.edit_text("\n".join(lines), reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("buy_item_"))
async def cb_buy_item(cb: CallbackQuery):
    item_id = int(cb.data.split("_")[2])
    item = await db.fetchone("SELECT * FROM items WHERE id=$1 AND is_available=TRUE", item_id)
    hero = await db.fetchone("SELECT * FROM heroes WHERE user_id=$1", cb.from_user.id)
    if not item or not hero:
        await cb.answer("Tidak ditemukan!", show_alert=True)
        return
    if hero["gold"] < item["price"]:
        await cb.answer(f"Gold tidak cukup! Butuh {item['price']:,} gold.", show_alert=True)
        return
    await db.execute("UPDATE heroes SET gold=gold-$1 WHERE user_id=$2", item["price"], cb.from_user.id)
    await db.execute("""
        INSERT INTO hero_items (user_id, item_id, quantity) VALUES ($1, $2, 1)
        ON CONFLICT DO NOTHING
    """, cb.from_user.id, item_id)
    await cb.answer(f"✅ {item['name']} dibeli! Cek inventory di /hero.", show_alert=True)

@router.callback_query(F.data == "shop_back")
async def cb_shop_back(cb: CallbackQuery):
    kb = InlineKeyboardBuilder()
    kb.button(text="🗡️ Senjata", callback_data="shop_weapons")
    kb.button(text="🎒 Item", callback_data="shop_items")
    kb.adjust(2)
    await cb.message.edit_text("🛍️ <b>Toko</b>\nBeli senjata dan item!", reply_markup=kb.as_markup())
