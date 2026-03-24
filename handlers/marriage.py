from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from services import database as db

router = Router()

@router.message(Command("marry", "nikah"))
async def cmd_marry(msg: Message):
    hero = await db.fetchone("SELECT * FROM heroes WHERE user_id=$1", msg.from_user.id)
    if not hero:
        await msg.answer("❌ Kamu belum punya hero! /start")
        return

    # Check if already married
    marriage = await db.fetchone("""
        SELECT m.*, u.full_name as partner_name, h.name as partner_hero
        FROM marriages m
        JOIN users u ON (m.user_a=$1 AND u.id=m.user_b) OR (m.user_b=$1 AND u.id=m.user_a)
        JOIN heroes h ON h.user_id=u.id
        WHERE m.user_a=$1 OR m.user_b=$1
    """, msg.from_user.id)

    if marriage:
        kb = InlineKeyboardBuilder()
        kb.button(text="💔 Cerai", callback_data=f"divorce_{msg.from_user.id}")
        await msg.answer(
            f"💑 <b>Status Pernikahan</b>\n\n"
            f"Kamu menikah dengan <b>{marriage['partner_name']}</b>\n"
            f"Hero: {marriage['partner_hero']}\n"
            f"Menikah sejak: {marriage['married_at'].strftime('%d/%m/%Y')}\n\n"
            f"Bonus: +10% EXP bersama saat dungeon!",
            reply_markup=kb.as_markup()
        )
        return

    args = msg.text.split()
    if len(args) < 2:
        await msg.answer(
            "💑 <b>Sistem Pernikahan</b>\n\n"
            "Menikah memberikan bonus +10% EXP!\n\n"
            "Format: /marry @username\n"
            "atau reply pesan seseorang dengan /marry"
        )
        return

    target_username = args[1].replace("@", "")
    target_user = await db.fetchone("SELECT * FROM users WHERE username=$1", target_username)

    if not target_user:
        await msg.answer("❌ User tidak ditemukan! Pastikan mereka sudah pernah pakai bot ini.")
        return

    if target_user["id"] == msg.from_user.id:
        await msg.answer("❌ Tidak bisa menikah dengan diri sendiri!")
        return

    target_married = await db.fetchone(
        "SELECT id FROM marriages WHERE user_a=$1 OR user_b=$1", target_user["id"]
    )
    if target_married:
        await msg.answer("❌ User tersebut sudah menikah.")
        return

    if hero["gold"] < 500:
        await msg.answer("❌ Butuh 500 gold untuk melamar!")
        return

    target_hero = await db.fetchone("SELECT name FROM heroes WHERE user_id=$1", target_user["id"])
    if not target_hero:
        await msg.answer("❌ Target belum punya hero!")
        return

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Terima Lamaran", callback_data=f"accept_marry_{msg.from_user.id}_{target_user['id']}")
    kb.button(text="❌ Tolak", callback_data=f"reject_marry_{msg.from_user.id}")
    kb.adjust(2)

    try:
        await msg.bot.send_message(
            target_user["id"],
            f"💍 <b>LAMARAN!</b>\n\n"
            f"<b>{hero['name']}</b> melamar kamu!\n"
            f"Terima lamarannya?",
            reply_markup=kb.as_markup()
        )
        await msg.answer(f"💌 Lamaran dikirim ke <b>@{target_username}</b>!")
    except Exception:
        await msg.answer("❌ Tidak bisa mengirim pesan ke user tersebut.")

@router.callback_query(F.data.startswith("accept_marry_"))
async def cb_accept_marry(cb: CallbackQuery):
    parts = cb.data.split("_")
    proposer_id = int(parts[2])
    target_id = int(parts[3])

    if cb.from_user.id != target_id:
        await cb.answer("Ini bukan untukmu!", show_alert=True)
        return

    # Check both free
    for uid in [proposer_id, target_id]:
        existing = await db.fetchone("SELECT id FROM marriages WHERE user_a=$1 OR user_b=$1", uid)
        if existing:
            await cb.answer("Salah satu sudah menikah!", show_alert=True)
            return

    await db.execute("UPDATE heroes SET gold=gold-500 WHERE user_id=$1", proposer_id)
    await db.execute("""
        INSERT INTO marriages (user_a, user_b) VALUES ($1, $2)
    """, proposer_id, target_id)
    await db.execute("UPDATE heroes SET married_to=$1 WHERE user_id=$2", target_id, proposer_id)
    await db.execute("UPDATE heroes SET married_to=$1 WHERE user_id=$2", proposer_id, target_id)

    proposer = await db.fetchone("SELECT name FROM heroes WHERE user_id=$1", proposer_id)
    target_hero = await db.fetchone("SELECT name FROM heroes WHERE user_id=$1", target_id)

    await cb.message.edit_text(
        f"💑 <b>PERNIKAHAN!</b>\n\n"
        f"<b>{proposer['name']}</b> & <b>{target_hero['name']}</b>\n"
        f"resmi menikah! Selamat! 🎉\n\n"
        f"Bonus: +10% EXP bersama saat dungeon!"
    )

    try:
        await cb.bot.send_message(
            proposer_id,
            f"🎊 Lamaranmu diterima oleh <b>{target_hero['name']}</b>!\n"
            f"Selamat! 💑"
        )
    except Exception:
        pass

@router.callback_query(F.data.startswith("reject_marry_"))
async def cb_reject_marry(cb: CallbackQuery):
    proposer_id = int(cb.data.split("_")[2])
    await cb.message.edit_text("💔 Lamaran ditolak.")
    try:
        await cb.bot.send_message(proposer_id, "💔 Lamaranmu ditolak.")
    except Exception:
        pass

@router.callback_query(F.data.startswith("divorce_"))
async def cb_divorce(cb: CallbackQuery):
    user_id = int(cb.data.split("_")[1])
    if cb.from_user.id != user_id:
        await cb.answer("Ini bukan akunmu!", show_alert=True)
        return

    marriage = await db.fetchone("SELECT * FROM marriages WHERE user_a=$1 OR user_b=$1", user_id)
    if not marriage:
        await cb.answer("Kamu tidak menikah!", show_alert=True)
        return

    partner_id = marriage["user_b"] if marriage["user_a"] == user_id else marriage["user_a"]
    await db.execute("DELETE FROM marriages WHERE id=$1", marriage["id"])
    await db.execute("UPDATE heroes SET married_to=NULL WHERE user_id=$1 OR user_id=$2", user_id, partner_id)

    await cb.message.edit_text("💔 Kamu telah bercerai.")
    try:
        await cb.bot.send_message(partner_id, "💔 Pasanganmu mengajukan cerai.")
    except Exception:
        pass
