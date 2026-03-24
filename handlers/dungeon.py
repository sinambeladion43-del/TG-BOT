import asyncio
import random
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from services import database as db
from utils.helpers import check_cooldown, set_cooldown, format_seconds, exp_to_next, RARITY_EMOJI, loot_roll

router = Router()
DUNGEON_COOLDOWN = 14400  # 4 jam

@router.message(Command("dungeon", "d"))
async def cmd_dungeon(msg: Message):
    hero = await db.fetchone("SELECT * FROM heroes WHERE user_id=$1", msg.from_user.id)
    if not hero:
        await msg.answer("❌ Kamu belum punya hero! /start")
        return

    cd = await check_cooldown(msg.from_user.id, "dungeon")
    if cd > 0:
        await msg.answer(f"⏳ Cooldown dungeon: <b>{format_seconds(cd)}</b> lagi.")
        return

    dungeons = await db.fetchall("SELECT * FROM dungeons ORDER BY min_level")
    kb = InlineKeyboardBuilder()
    lines = ["🏰 <b>Pilih Dungeon</b>\n"]
    for d in dungeons:
        can_enter = hero["level"] >= d["min_level"]
        status = "" if can_enter else f" (Lv.{d['min_level']}+)"
        lines.append(f"{'✅' if can_enter else '🔒'} <b>{d['name']}</b>{status}")
        lines.append(f"   👾 {d['enemy_name']} | 🏆 +{d['exp_reward']} EXP | 💰 +{d['gold_reward']} Gold")
        if can_enter:
            kb.button(text=f"Masuk: {d['name']}", callback_data=f"enter_dungeon_{d['id']}")
    kb.adjust(1)
    await msg.answer("\n".join(lines), reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("enter_dungeon_"))
async def cb_enter_dungeon(cb: CallbackQuery):
    dungeon_id = int(cb.data.split("_")[2])
    hero = await db.fetchone("SELECT * FROM heroes WHERE user_id=$1", cb.from_user.id)
    dungeon = await db.fetchone("SELECT * FROM dungeons WHERE id=$1", dungeon_id)

    if not hero or not dungeon:
        await cb.answer("Data tidak ditemukan!", show_alert=True)
        return

    cd = await check_cooldown(cb.from_user.id, "dungeon")
    if cd > 0:
        await cb.answer(f"⏳ Cooldown: {format_seconds(cd)} lagi.", show_alert=True)
        return

    if hero["level"] < dungeon["min_level"]:
        await cb.answer(f"Level tidak cukup! Butuh Lv.{dungeon['min_level']}", show_alert=True)
        return

    # Get equipment bonuses
    weapon_atk = await db.fetchval("""
        SELECT COALESCE(SUM(w.atk_bonus),0) FROM weapons w
        JOIN hero_weapons hw ON hw.weapon_id=w.id
        WHERE hw.user_id=$1 AND hw.equipped=TRUE
    """, cb.from_user.id) or 0
    item_def = await db.fetchval("""
        SELECT COALESCE(SUM(i.def_bonus),0) FROM items i
        JOIN hero_items hi ON hi.item_id=i.id
        WHERE hi.user_id=$1 AND hi.equipped=TRUE
    """, cb.from_user.id) or 0

    hero_atk = hero["atk"] + weapon_atk
    hero_def = hero["def"] + item_def
    hero_hp = hero["hp"]
    enemy_hp = dungeon["enemy_hp"]

    # Animated battle
    msg_text = f"⚔️ <b>{dungeon['name']}</b>\n\n"
    if dungeon.get("photo_id"):
        battle_msg = await cb.message.answer_photo(dungeon["photo_id"], caption=msg_text + "Pertarungan dimulai...")
    else:
        battle_msg = await cb.message.answer(msg_text + "Pertarungan dimulai...")

    log = []
    rounds = 0
    while hero_hp > 0 and enemy_hp > 0 and rounds < 25:
        # Hero attack
        crit = random.random() < 0.1
        dmg = max(1, hero_atk + random.randint(-2, 3))
        if crit:
            dmg = int(dmg * 1.5)
        enemy_hp -= dmg
        log_line = f"{'💥 KRITIS! ' if crit else ''}Kamu serang -{dmg} HP"
        log.append(log_line)

        if enemy_hp <= 0:
            break

        # Enemy attack
        take = max(1, dungeon["enemy_atk"] - hero_def + random.randint(-2, 2))
        hero_hp -= take
        log.append(f"👾 {dungeon['enemy_name']} serang -{take} HP")
        rounds += 1

    won = enemy_hp <= 0
    # Double exp/gold check
    double_exp = await db.fetchval("SELECT value FROM settings WHERE key='double_exp'") == "true"
    double_gold = await db.fetchval("SELECT value FROM settings WHERE key='double_gold'") == "true"

    exp_gain = dungeon["exp_reward"] if won else dungeon["exp_reward"] // 4
    gold_gain = dungeon["gold_reward"] if won else 0
    if double_exp: exp_gain *= 2
    if double_gold: gold_gain *= 2

    result_text = msg_text
    result_text += "\n".join(log[-8:]) + "\n\n"

    if won:
        # Check loot
        loot_rarity = loot_roll()
        loot_item = await db.fetchone(
            "SELECT * FROM items WHERE rarity=$1 AND is_available=TRUE ORDER BY RANDOM() LIMIT 1",
            loot_rarity
        )
        result_text += f"✅ <b>MENANG!</b>\n+{exp_gain} EXP | +{gold_gain} Gold"
        if double_exp: result_text += " (2x EXP!)"
        if double_gold: result_text += " (2x Gold!)"

        if loot_item:
            result_text += f"\n🎁 Loot: {RARITY_EMOJI.get(loot_rarity,'')} <b>{loot_item['name']}</b>!"
            await db.execute("""
                INSERT INTO hero_items (user_id, item_id, quantity)
                VALUES ($1, $2, 1)
                ON CONFLICT DO NOTHING
            """, cb.from_user.id, loot_item["id"])

        # Level up check
        new_exp = hero["exp"] + exp_gain
        leveled = False
        new_level = hero["level"]
        new_talent = hero["talent_points"]
        while new_exp >= exp_to_next(new_level):
            new_exp -= exp_to_next(new_level)
            new_level += 1
            leveled = True
            if new_level % 5 == 0:
                new_talent += 1

        await db.execute("""
            UPDATE heroes SET
                exp=$1, level=$2, gold=gold+$3,
                hp=LEAST(hp+20, max_hp),
                dungeons_done=dungeons_done+1,
                total_damage=total_damage+$4,
                talent_points=$5
            WHERE user_id=$6
        """, new_exp, new_level, gold_gain, dungeon["enemy_hp"] - max(enemy_hp, 0), new_talent, cb.from_user.id)

        if leveled:
            hp_up = (new_level - hero["level"]) * 20
            await db.execute("""
                UPDATE heroes SET max_hp=max_hp+$1, hp=max_hp WHERE user_id=$2
            """, hp_up, cb.from_user.id)
            if new_talent > hero["talent_points"]:
                result_text += f"\n⬆️ <b>LEVEL UP! Lv.{new_level}</b> 🎉\n🌳 +1 Talent Point!"
            else:
                result_text += f"\n⬆️ <b>LEVEL UP! Lv.{new_level}</b> 🎉"
    else:
        result_text += f"❌ <b>KALAH!</b>\n+{exp_gain} EXP (hiburan)"
        await db.execute("""
            UPDATE heroes SET
                exp=exp+$1, losses=losses+1,
                hp=GREATEST(hp-$2, 1)
            WHERE user_id=$3
        """, exp_gain, dungeon["enemy_atk"] * 2, cb.from_user.id)

    await set_cooldown(cb.from_user.id, "dungeon", DUNGEON_COOLDOWN)
    await db.execute("UPDATE heroes SET wins=wins+1 WHERE user_id=$1" if won else
                     "UPDATE heroes SET losses=losses+1 WHERE user_id=$1", cb.from_user.id)

    kb = InlineKeyboardBuilder()
    kb.button(text="⚔️ Hero", callback_data=f"back_hero_{cb.from_user.id}")
    kb.button(text="🔙 Dungeon Lain", callback_data="reload_dungeon")
    kb.adjust(2)

    try:
        if dungeon.get("photo_id"):
            await battle_msg.edit_caption(result_text, reply_markup=kb.as_markup())
        else:
            await battle_msg.edit_text(result_text, reply_markup=kb.as_markup())
    except Exception:
        await cb.message.answer(result_text, reply_markup=kb.as_markup())

@router.callback_query(F.data == "reload_dungeon")
async def cb_reload_dungeon(cb: CallbackQuery):
    await cmd_dungeon(cb.message)
