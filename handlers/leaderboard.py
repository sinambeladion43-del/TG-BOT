from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from services import database as db
from utils.helpers import CLASS_EMOJI

router = Router()

MEDALS = ["🥇", "🥈", "🥉"] + ["4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]

@router.message(Command("top", "leaderboard", "lb"))
async def cmd_leaderboard(msg: Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="⚡ Top Power", callback_data="lb_power")
    kb.button(text="⭐ Top Level", callback_data="lb_level")
    kb.button(text="💰 Top Gold", callback_data="lb_gold")
    kb.button(text="🏆 Top Wins", callback_data="lb_wins")
    kb.button(text="🏰 Top Guild", callback_data="lb_guild")
    kb.button(text="⚔️ Top Dungeon", callback_data="lb_dungeon")
    kb.adjust(2, 2, 2)
    await msg.answer("🏆 <b>Top Global</b>\nPilih kategori:", reply_markup=kb.as_markup())

@router.callback_query(F.data == "lb_power")
async def lb_power(cb: CallbackQuery):
    rows = await db.fetchall("""
        SELECT h.name, h.level, h.hero_class,
               (h.atk*h.level+h.def+h.hp/10) as bp,
               u.full_name
        FROM heroes h JOIN users u ON u.id=h.user_id
        ORDER BY bp DESC LIMIT 10
    """)
    lines = ["⚡ <b>Top 10 Battle Power</b>\n"]
    for i, r in enumerate(rows):
        medal = MEDALS[i] if i < len(MEDALS) else f"{i+1}."
        you = " ← Kamu" if r.get("user_id") == cb.from_user.id else ""
        lines.append(f"{medal} <b>{r['name']}</b> {CLASS_EMOJI.get(r['hero_class'],'')} Lv.{r['level']}")
        lines.append(f"   ⚡ {r['bp']:,} BP{you}")
    await send_lb(cb, "\n".join(lines))

@router.callback_query(F.data == "lb_level")
async def lb_level(cb: CallbackQuery):
    rows = await db.fetchall("""
        SELECT h.name, h.level, h.hero_class, h.exp, u.id as uid
        FROM heroes h JOIN users u ON u.id=h.user_id
        ORDER BY h.level DESC, h.exp DESC LIMIT 10
    """)
    lines = ["⭐ <b>Top 10 Level</b>\n"]
    for i, r in enumerate(rows):
        medal = MEDALS[i] if i < len(MEDALS) else f"{i+1}."
        you = " ← Kamu" if r["uid"] == cb.from_user.id else ""
        lines.append(f"{medal} <b>{r['name']}</b> {CLASS_EMOJI.get(r['hero_class'],'')} — Lv.<b>{r['level']}</b>{you}")
    await send_lb(cb, "\n".join(lines))

@router.callback_query(F.data == "lb_gold")
async def lb_gold(cb: CallbackQuery):
    rows = await db.fetchall("""
        SELECT h.name, h.gold, h.level, u.id as uid
        FROM heroes h JOIN users u ON u.id=h.user_id
        ORDER BY h.gold DESC LIMIT 10
    """)
    lines = ["💰 <b>Top 10 Terkaya</b>\n"]
    for i, r in enumerate(rows):
        medal = MEDALS[i] if i < len(MEDALS) else f"{i+1}."
        you = " ← Kamu" if r["uid"] == cb.from_user.id else ""
        lines.append(f"{medal} <b>{r['name']}</b> Lv.{r['level']} — 💰 <b>{r['gold']:,}</b> gold{you}")
    await send_lb(cb, "\n".join(lines))

@router.callback_query(F.data == "lb_wins")
async def lb_wins(cb: CallbackQuery):
    rows = await db.fetchall("""
        SELECT h.name, h.wins, h.losses, h.level, u.id as uid
        FROM heroes h JOIN users u ON u.id=h.user_id
        ORDER BY h.wins DESC LIMIT 10
    """)
    lines = ["🏆 <b>Top 10 Wins</b>\n"]
    for i, r in enumerate(rows):
        medal = MEDALS[i] if i < len(MEDALS) else f"{i+1}."
        you = " ← Kamu" if r["uid"] == cb.from_user.id else ""
        lines.append(f"{medal} <b>{r['name']}</b> — 🏆 {r['wins']}W / {r['losses']}L{you}")
    await send_lb(cb, "\n".join(lines))

@router.callback_query(F.data == "lb_dungeon")
async def lb_dungeon(cb: CallbackQuery):
    rows = await db.fetchall("""
        SELECT h.name, h.dungeons_done, h.level, u.id as uid
        FROM heroes h JOIN users u ON u.id=h.user_id
        ORDER BY h.dungeons_done DESC LIMIT 10
    """)
    lines = ["⚔️ <b>Top 10 Dungeon Runs</b>\n"]
    for i, r in enumerate(rows):
        medal = MEDALS[i] if i < len(MEDALS) else f"{i+1}."
        you = " ← Kamu" if r["uid"] == cb.from_user.id else ""
        lines.append(f"{medal} <b>{r['name']}</b> Lv.{r['level']} — 🏰 {r['dungeons_done']} runs{you}")
    await send_lb(cb, "\n".join(lines))

@router.callback_query(F.data == "lb_guild")
async def lb_guild(cb: CallbackQuery):
    rows = await db.fetchall("""
        SELECT g.name, g.wins, g.level,
               COUNT(h.user_id) as members,
               COALESCE(SUM(h.atk*h.level+h.def+h.hp/10),0) as power
        FROM guilds g LEFT JOIN heroes h ON h.guild_id=g.id
        GROUP BY g.id ORDER BY power DESC LIMIT 10
    """)
    lines = ["🏰 <b>Top 10 Guild</b>\n"]
    for i, r in enumerate(rows):
        medal = MEDALS[i] if i < len(MEDALS) else f"{i+1}."
        lines.append(
            f"{medal} <b>{r['name']}</b> Lv.{r['level']}\n"
            f"   ⚡ {r['power']:,} | 👥 {r['members']} | 🏆 {r['wins']}W"
        )
    await send_lb(cb, "\n".join(lines))

async def send_lb(cb: CallbackQuery, text: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="⚡ Power", callback_data="lb_power")
    kb.button(text="⭐ Level", callback_data="lb_level")
    kb.button(text="💰 Gold", callback_data="lb_gold")
    kb.button(text="🏆 Wins", callback_data="lb_wins")
    kb.button(text="🏰 Guild", callback_data="lb_guild")
    kb.button(text="⚔️ Dungeon", callback_data="lb_dungeon")
    kb.adjust(3, 3)
    await cb.message.edit_text(text, reply_markup=kb.as_markup())
