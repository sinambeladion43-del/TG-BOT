from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from services import database as db
from utils.helpers import RARITY_EMOJI

router = Router()

class MarketState(StatesGroup):
    select_item = State()
    set_price = State()

@router.message(Command("market", "pasar"))
async def cmd_market(msg: Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="🛒 Lihat Listing", callback_data="market_browse_item")
    kb.button(text="⚔️ Lihat Senjata", callback_data="market_browse_weapon")
    kb.button(text="📦 Jual Item", callback_data="market_sell_item")
    kb.button(text="🗡️ Jual Senjata", callback_data="market_sell_weapon")
    kb.button(text="📋 Listing Saya", callback_data=f"market_mylist_{msg.from_user.id}")
    kb.adjust(2, 2, 1)
    await msg.answer(
        "🏪 <b>Market</b>\n\nBeli dan jual item/senjata dengan sesama pemain!",
        reply_markup=kb.as_markup()
    )

@router.callback_query(F.data == "market_browse_item")
async def cb_browse_items(cb: CallbackQuery):
    listings = await db.fetchall("""
        SELECT ml.id, ml.price, ml.quantity, ml.seller_id,
               i.name, i.rarity, i.atk_bonus, i.def_bonus, i.hp_bonus,
               u.full_name as seller_name
        FROM market_listings ml
        JOIN items i ON i.id=ml.item_id
        JOIN users u ON u.id=ml.seller_id
        WHERE ml.is_sold=FALSE AND ml.item_type='item'
        ORDER BY ml.listed_at DESC LIMIT 15
    """)

    if not listings:
        await cb.answer("Tidak ada item dijual saat ini.", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    lines = ["🛒 <b>Market - Item</b>\n"]
    for l in listings:
        lines.append(
            f"{RARITY_EMOJI.get(l['rarity'],'')} <b>{l['name']}</b> x{l['quantity']}\n"
            f"   💰 {l['price']:,} gold | Penjual: {l['seller_name']}"
        )
        if l["seller_id"] != cb.from_user.id:
            kb.button(text=f"Beli {l['name']} ({l['price']:,}g)", callback_data=f"market_buy_{l['id']}")
    kb.button(text="🔙 Kembali", callback_data="market_back")
    kb.adjust(1)
    await cb.message.edit_text("\n".join(lines), reply_markup=kb.as_markup())

@router.callback_query(F.data == "market_browse_weapon")
async def cb_browse_weapons(cb: CallbackQuery):
    listings = await db.fetchall("""
        SELECT ml.id, ml.price, ml.seller_id,
               w.name, w.rarity, w.atk_bonus,
               u.full_name as seller_name
        FROM market_listings ml
        JOIN weapons w ON w.id=ml.item_id
        JOIN users u ON u.id=ml.seller_id
        WHERE ml.is_sold=FALSE AND ml.item_type='weapon'
        ORDER BY ml.listed_at DESC LIMIT 15
    """)

    if not listings:
        await cb.answer("Tidak ada senjata dijual saat ini.", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    lines = ["⚔️ <b>Market - Senjata</b>\n"]
    for l in listings:
        lines.append(
            f"{RARITY_EMOJI.get(l['rarity'],'')} <b>{l['name']}</b> (+{l['atk_bonus']} ATK)\n"
            f"   💰 {l['price']:,} gold | Penjual: {l['seller_name']}"
        )
        if l["seller_id"] != cb.from_user.id:
            kb.button(text=f"Beli {l['name']} ({l['price']:,}g)", callback_data=f"market_buy_{l['id']}")
    kb.button(text="🔙 Kembali", callback_data="market_back")
    kb.adjust(1)
    await cb.message.edit_text("\n".join(lines), reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("market_buy_"))
async def cb_market_buy(cb: CallbackQuery):
    listing_id = int(cb.data.split("_")[2])
    listing = await db.fetchone("""
        SELECT ml.*, i.name as iname FROM market_listings ml
        LEFT JOIN items i ON i.id=ml.item_id AND ml.item_type='item'
        WHERE ml.id=$1 AND ml.is_sold=FALSE
    """, listing_id)

    if not listing:
        await cb.answer("Listing sudah tidak ada!", show_alert=True)
        return
    if listing["seller_id"] == cb.from_user.id:
        await cb.answer("Tidak bisa beli barang sendiri!", show_alert=True)
        return

    buyer = await db.fetchone("SELECT * FROM heroes WHERE user_id=$1", cb.from_user.id)
    if not buyer or buyer["gold"] < listing["price"]:
        await cb.answer(f"Gold tidak cukup! Butuh {listing['price']:,} gold.", show_alert=True)
        return

    # Transaksi
    await db.execute("UPDATE market_listings SET is_sold=TRUE WHERE id=$1", listing_id)
    await db.execute("UPDATE heroes SET gold=gold-$1 WHERE user_id=$2", listing["price"], cb.from_user.id)
    await db.execute("UPDATE heroes SET gold=gold+$1 WHERE user_id=$2", listing["price"], listing["seller_id"])

    if listing["item_type"] == "item":
        await db.execute("""
            INSERT INTO hero_items (user_id, item_id, quantity)
            VALUES ($1, $2, $3)
            ON CONFLICT DO NOTHING
        """, cb.from_user.id, listing["item_id"], listing["quantity"])
    else:
        await db.execute("""
            INSERT INTO hero_weapons (user_id, weapon_id)
            VALUES ($1, $2)
        """, cb.from_user.id, listing["item_id"])

    # Notif penjual
    try:
        buyer_name = (await db.fetchone("SELECT full_name FROM users WHERE id=$1", cb.from_user.id))["full_name"]
        item_name = listing.get("iname") or "senjata"
        await cb.bot.send_message(
            listing["seller_id"],
            f"💰 Item kamu <b>{item_name}</b> terjual!\n"
            f"Pembeli: {buyer_name}\n"
            f"+{listing['price']:,} gold"
        )
    except Exception:
        pass

    await cb.answer(f"✅ Berhasil dibeli! -{listing['price']:,} gold", show_alert=True)
    await cb_browse_items(cb)

@router.callback_query(F.data == "market_sell_item")
async def cb_sell_item(cb: CallbackQuery, state: FSMContext):
    items = await db.fetchall("""
        SELECT hi.id as slot_id, i.name, i.rarity, i.id as item_id
        FROM hero_items hi JOIN items i ON i.id=hi.item_id
        WHERE hi.user_id=$1 AND hi.equipped=FALSE
    """, cb.from_user.id)

    if not items:
        await cb.answer("Tidak ada item untuk dijual!", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    for it in items:
        kb.button(text=f"{RARITY_EMOJI.get(it['rarity'],'')} {it['name']}", callback_data=f"market_list_item_{it['item_id']}_{it['slot_id']}")
    kb.button(text="🔙 Kembali", callback_data="market_back")
    kb.adjust(1)
    await cb.message.edit_text("📦 Pilih item untuk dijual:", reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("market_list_item_"))
async def cb_list_item(cb: CallbackQuery, state: FSMContext):
    parts = cb.data.split("_")
    item_id = int(parts[3])
    slot_id = int(parts[4])
    await state.update_data(list_item_id=item_id, list_slot_id=slot_id, list_type="item")
    await cb.message.edit_text("💰 Masukkan harga jual (gold):")
    await state.set_state(MarketState.set_price)

@router.callback_query(F.data == "market_sell_weapon")
async def cb_sell_weapon(cb: CallbackQuery, state: FSMContext):
    weapons = await db.fetchall("""
        SELECT hw.id as slot_id, w.name, w.rarity, w.id as weapon_id
        FROM hero_weapons hw JOIN weapons w ON w.id=hw.weapon_id
        WHERE hw.user_id=$1 AND hw.equipped=FALSE
    """, cb.from_user.id)

    if not weapons:
        await cb.answer("Tidak ada senjata untuk dijual!", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    for w in weapons:
        kb.button(text=f"{RARITY_EMOJI.get(w['rarity'],'')} {w['name']}", callback_data=f"market_list_weapon_{w['weapon_id']}_{w['slot_id']}")
    kb.button(text="🔙 Kembali", callback_data="market_back")
    kb.adjust(1)
    await cb.message.edit_text("🗡️ Pilih senjata untuk dijual:", reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("market_list_weapon_"))
async def cb_list_weapon(cb: CallbackQuery, state: FSMContext):
    parts = cb.data.split("_")
    weapon_id = int(parts[3])
    slot_id = int(parts[4])
    await state.update_data(list_item_id=weapon_id, list_slot_id=slot_id, list_type="weapon")
    await cb.message.edit_text("💰 Masukkan harga jual (gold):")
    await state.set_state(MarketState.set_price)

@router.message(MarketState.set_price)
async def market_set_price(msg: Message, state: FSMContext):
    try:
        price = int(msg.text.strip())
        if price < 1 or price > 9999999:
            await msg.answer("❌ Harga harus antara 1 dan 9,999,999 gold.")
            return
    except ValueError:
        await msg.answer("❌ Masukkan angka yang valid.")
        return

    data = await state.get_data()
    item_id = data["list_item_id"]
    slot_id = data["list_slot_id"]
    list_type = data["list_type"]

    await db.execute("""
        INSERT INTO market_listings (seller_id, item_id, item_type, price)
        VALUES ($1, $2, $3, $4)
    """, msg.from_user.id, item_id, list_type, price)

    # Hapus dari inventory
    if list_type == "item":
        await db.execute("DELETE FROM hero_items WHERE id=$1", slot_id)
    else:
        await db.execute("DELETE FROM hero_weapons WHERE id=$1", slot_id)

    await state.clear()
    await msg.answer(f"✅ Item berhasil didaftarkan di market dengan harga <b>{price:,} gold</b>!")

@router.callback_query(F.data.startswith("market_mylist_"))
async def cb_my_listings(cb: CallbackQuery):
    user_id = int(cb.data.split("_")[2])
    listings = await db.fetchall("""
        SELECT ml.id, ml.price, ml.item_type,
               COALESCE(i.name, w.name) as name
        FROM market_listings ml
        LEFT JOIN items i ON i.id=ml.item_id AND ml.item_type='item'
        LEFT JOIN weapons w ON w.id=ml.item_id AND ml.item_type='weapon'
        WHERE ml.seller_id=$1 AND ml.is_sold=FALSE
    """, user_id)

    if not listings:
        await cb.answer("Kamu tidak punya listing aktif.", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    lines = ["📋 <b>Listing Aktif Kamu</b>\n"]
    for l in listings:
        lines.append(f"• {l['name']} — {l['price']:,} gold")
        kb.button(text=f"❌ Tarik {l['name']}", callback_data=f"market_cancel_{l['id']}")
    kb.button(text="🔙 Kembali", callback_data="market_back")
    kb.adjust(1)
    await cb.message.edit_text("\n".join(lines), reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("market_cancel_"))
async def cb_cancel_listing(cb: CallbackQuery):
    listing_id = int(cb.data.split("_")[2])
    listing = await db.fetchone("SELECT * FROM market_listings WHERE id=$1 AND is_sold=FALSE", listing_id)
    if not listing or listing["seller_id"] != cb.from_user.id:
        await cb.answer("Listing tidak ditemukan!", show_alert=True)
        return

    await db.execute("DELETE FROM market_listings WHERE id=$1", listing_id)

    # Return item to inventory
    if listing["item_type"] == "item":
        await db.execute("""
            INSERT INTO hero_items (user_id, item_id, quantity) VALUES ($1, $2, 1)
            ON CONFLICT DO NOTHING
        """, cb.from_user.id, listing["item_id"])
    else:
        await db.execute("INSERT INTO hero_weapons (user_id, weapon_id) VALUES ($1, $2)",
                         cb.from_user.id, listing["item_id"])

    await cb.answer("✅ Listing dibatalkan, item dikembalikan ke inventory.")
    cb.data = f"market_mylist_{cb.from_user.id}"
    await cb_my_listings(cb)

@router.callback_query(F.data == "market_back")
async def cb_market_back(cb: CallbackQuery):
    kb = InlineKeyboardBuilder()
    kb.button(text="🛒 Lihat Item", callback_data="market_browse_item")
    kb.button(text="⚔️ Lihat Senjata", callback_data="market_browse_weapon")
    kb.button(text="📦 Jual Item", callback_data="market_sell_item")
    kb.button(text="🗡️ Jual Senjata", callback_data="market_sell_weapon")
    kb.button(text="📋 Listing Saya", callback_data=f"market_mylist_{cb.from_user.id}")
    kb.adjust(2, 2, 1)
    await cb.message.edit_text(
        "🏪 <b>Market</b>\n\nBeli dan jual item/senjata dengan sesama pemain!",
        reply_markup=kb.as_markup()
    )
