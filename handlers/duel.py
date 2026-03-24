import random
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from services import database as db
from utils.helpers import check_cooldown, set_cooldown, format_seconds

router = Router()
DUEL_COOLDOWN = 3600  # 1 jam

@router.message(Command("duel"))
async def cmd_duel(msg: Message):
    hero = await db.fetchone("SELECT * FROM heroes WHERE user_id=$1", msg.from_user.id)
    if not hero:
        await msg.answer("❌ Kamu belum punya hero! /start")
        return

    cd = await check_cooldown(msg.from_user.id, "duel")
    if cd > 0:
        await msg.answer(f"⏳ Cooldown duel: <b>{format_seconds(cd)}</b> lagi.")
        return

    args = msg.text.split()
    if len(args) < 2:
        await msg.answer("Format: /duel @username\nAtau reply pesan dengan /duel")
        return

    target_username = args[1].replace("@", "")
    target_user = await db.fetchone("SELECT * FROM users WHERE username=$1", target_username)
    if not target_user:
        await msg.answer("❌ User tidak ditemukan!")
        return
    if target_user["id"] == msg.from_user.id:
        await msg.answer("❌ Tidak bisa duel diri sendiri!")
        return

    target_hero = await db.fetchone("SELECT * FROM heroes WHERE user_id=$1", target_user["id"])
    if not target_hero:
        await msg.answer("❌ Target belum punya hero!")
        return

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Terima Duel", callback_data=f"accept_duel_{msg.from_user.id}_{target_user['id']}")
    kb.button(text="❌ Tolak", callback_data=f"reject_duel_{msg.from_user.id}")
    kb.adjust(2)

    try:
        await msg.bot.send_message(
            target_user["id"],
            f"⚔️ <b>TANTANGAN DUEL!</b>\n\n"
            f"<b>{hero['name']}</b> (Lv.{hero['level']}) menantang kamu!\n"
            f"Terima tantangannya?",
            reply_markup=kb.as_markup()
        )
        await msg.answer(f"⚔️ Tantangan duel dikirim ke <b>@{target_username}</b>!")
    except Exception:
        await msg.answer("❌ Tidak bisa mengirim tantangan ke user tersebut.")

@router.callback_query(F.data.startswith("accept_duel_"))
async def cb_accept_duel(cb: CallbackQuery):
    parts = cb.data.split("_")
    challenger_id = int(parts[2])
    target_id = int(parts[3])

    if cb.from_user.id != target_id:
        await cb.answer("Ini bukan untukmu!", show_alert=True)
        return

    challenger = await db.fetchone("SELECT * FROM heroes WHERE user_id=$1", challenger_id)
    target = await db.fetchone("SELECT * FROM heroes WHERE user_id=$1", target_id)

    if not challenger or not target:
        await cb.answer("Data tidak ditemukan!", show_alert=True)
        return

    # Get weapon bonuses
    def get_atk(hero_uid):
        return db.fetchval("""
            SELECT COALESCE(SUM(w.atk_bonus),0) FROM weapons w
            JOIN hero_weapons hw ON hw.weapon_id=w.id
            WHERE hw.user_id=$1 AND hw.equipped=TRUE
        """, hero_uid)

    c_bonus = 0
    t_bonus = 0

    # Simple battle simulation
    c_hp = challenger["hp"]
    t_hp = target["hp"]
    c_atk = challenger["atk"] + c_bonus
    t_atk = target["atk"] + t_bonus
    c_def = challenger["def"]
    t_def = target["def"]

    log = []
    rounds = 0
    # Determine who goes first by SPD
    c_first = challenger["spd"] >= target["spd"]

    while c_hp > 0 and t_hp > 0 and rounds < 20:
        if c_first:
            dmg = max(1, c_atk - t_def + random.randint(-2, 3))
            t_hp -= dmg
            log.append(f"⚔️ {challenger['name']} serang -{dmg}")
            if t_hp <= 0: break
            dmg2 = max(1, t_atk - c_def + random.randint(-2, 3))
            c_hp -= dmg2
            log.append(f"⚔️ {target['name']} serang -{dmg2}")
        else:
            dmg = max(1, t_atk - c_def + random.randint(-2, 3))
            c_hp -= dmg
            log.append(f"⚔️ {target['name']} serang -{dmg}")
            if c_hp <= 0: break
            dmg2 = max(1, c_atk - t_def + random.randint(-2, 3))
            t_hp -= dmg2
            log.append(f"⚔️ {challenger['name']} serang -{dmg2}")
        rounds += 1

    challenger_won = t_hp <= 0

    # Rewards
    gold_prize = min(50, (target["gold"] if not challenger_won else challenger["gold"]) // 10)
    exp_prize = 20

    if challenger_won:
        winner, loser = challenger, target
        winner_id, loser_id = challenger_id, target_id
    else:
        winner, loser = target, challenger
        winner_id, loser_id = target_id, challenger_id

    await db.execute("UPDATE heroes SET wins=wins+1, exp=exp+$1, gold=gold+$2 WHERE user_id=$3",
                     exp_prize, gold_prize, winner_id)
    await db.execute("UPDATE heroes SET losses=losses+1 WHERE user_id=$1", loser_id)

    await set_cooldown(challenger_id, "duel", DUEL_COOLDOWN)
    await set_cooldown(target_id, "duel", DUEL_COOLDOWN)

    result = (
        f"⚔️ <b>Hasil Duel!</b>\n\n"
        + "\n".join(log[-8:]) +
        f"\n\n🏆 Pemenang: <b>{winner['name']}</b>\n"
        f"+{exp_prize} EXP | +{gold_prize} gold"
    )

    await cb.message.edit_text(result)
    try:
        await cb.bot.send_message(challenger_id, result)
    except Exception:
        pass

@router.callback_query(F.data.startswith("reject_duel_"))
async def cb_reject_duel(cb: CallbackQuery):
    challenger_id = int(cb.data.split("_")[2])
    await cb.message.edit_text("❌ Tantangan duel ditolak.")
    try:
        await cb.bot.send_message(challenger_id, "❌ Tantangan duelmu ditolak.")
    except Exception:
        pass
