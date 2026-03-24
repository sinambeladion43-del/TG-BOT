from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from services import database as db
from utils.helpers import CLASS_BONUS, CLASS_EMOJI

router = Router()

class OnboardingState(StatesGroup):
    waiting_name = State()
    waiting_class = State()

def main_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="⚔️ Hero", callback_data="menu_hero")
    kb.button(text="🏰 Dungeon", callback_data="menu_dungeon")
    kb.button(text="👥 Guild", callback_data="menu_guild")
    kb.button(text="🏪 Market", callback_data="menu_market")
    kb.button(text="🛍️ Shop", callback_data="menu_shop")
    kb.button(text="🏆 Leaderboard", callback_data="menu_leaderboard")
    kb.button(text="💑 Nikah", callback_data="menu_marriage")
    kb.button(text="🌟 Daily", callback_data="menu_daily")
    kb.adjust(2, 2, 2, 2)
    return kb.as_markup()

@router.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext):
    hero = await db.fetchone("SELECT * FROM heroes WHERE user_id=$1", msg.from_user.id)
    if hero:
        await msg.answer(
            f"👋 Selamat datang kembali, <b>{hero['name']}</b>!\n"
            f"Level {hero['level']} {CLASS_EMOJI.get(hero['hero_class'], '')} {hero['hero_class'].capitalize()}\n\n"
            f"Pilih menu:",
            reply_markup=main_menu_kb()
        )
        return

    # Handle referral
    args = msg.text.split()
    if len(args) > 1 and args[1].startswith("REF"):
        ref_id = args[1].replace("REF", "")
        try:
            ref_id = int(ref_id)
            if ref_id != msg.from_user.id:
                await state.update_data(referral_by=ref_id)
        except ValueError:
            pass

    await msg.answer(
        "⚔️ <b>Selamat datang di RPG Kingdom!</b>\n\n"
        "Petualanganmu dimulai sekarang.\n"
        "Pertama, masukkan nama heromu:"
    )
    await state.set_state(OnboardingState.waiting_name)

@router.message(OnboardingState.waiting_name)
async def onboard_name(msg: Message, state: FSMContext):
    name = msg.text.strip()
    if len(name) < 2 or len(name) > 20:
        await msg.answer("❌ Nama harus antara 2-20 karakter.")
        return

    await state.update_data(hero_name=name)
    kb = InlineKeyboardBuilder()
    kb.button(text="⚔️ Warrior - Tank kuat", callback_data="class_warrior")
    kb.button(text="🔮 Mage - Damage tinggi", callback_data="class_mage")
    kb.button(text="🏹 Archer - Cepat & kritis", callback_data="class_archer")
    kb.adjust(1)
    await msg.answer(
        f"Nama heromu: <b>{name}</b>\n\nPilih kelasmu:",
        reply_markup=kb.as_markup()
    )
    await state.set_state(OnboardingState.waiting_class)

@router.callback_query(F.data.startswith("class_"), OnboardingState.waiting_class)
async def onboard_class(cb: CallbackQuery, state: FSMContext):
    hero_class = cb.data.replace("class_", "")
    data = await state.get_data()
    name = data.get("hero_name", "Hero")
    ref_by = data.get("referral_by")

    bonus = CLASS_BONUS[hero_class]
    hp = 100 + bonus["hp"]
    atk = 10 + bonus["atk"]
    def_ = 5 + bonus["def"]
    spd = 5 + bonus["spd"]

    await db.execute("""
        INSERT INTO heroes (user_id, name, hero_class, hp, max_hp, atk, def, spd, gold)
        VALUES ($1, $2, $3, $4, $4, $5, $6, $7, 500)
        ON CONFLICT (user_id) DO NOTHING
    """, cb.from_user.id, name, hero_class, hp, atk, def_, spd)

    if ref_by:
        await db.execute("UPDATE users SET referral_by=$1 WHERE id=$2", ref_by, cb.from_user.id)
        await db.execute("UPDATE users SET referral_count=referral_count+1 WHERE id=$1", ref_by)
        await db.execute("UPDATE heroes SET gold=gold+500 WHERE user_id=$1", ref_by)
        try:
            await cb.bot.send_message(ref_by,
                f"🎉 Temanmu bergabung lewat referral kamu!\n+500 gold bonus!"
            )
        except Exception:
            pass

    await state.clear()
    await cb.message.edit_text(
        f"🎉 <b>Hero dibuat!</b>\n\n"
        f"Nama: <b>{name}</b>\n"
        f"Kelas: <b>{CLASS_EMOJI[hero_class]} {hero_class.capitalize()}</b>\n"
        f"❤️ HP: {hp} | ⚔️ ATK: {atk} | 🛡️ DEF: {def_} | 💨 SPD: {spd}\n"
        f"💰 Gold awal: 500\n\n"
        f"Petualanganmu dimulai! Pilih menu:",
        reply_markup=main_menu_kb()
    )

@router.message(Command("menu"))
async def cmd_menu(msg: Message):
    hero = await db.fetchone("SELECT * FROM heroes WHERE user_id=$1", msg.from_user.id)
    if not hero:
        await msg.answer("Kamu belum punya hero! Ketik /start untuk memulai.")
        return
    await msg.answer(
        f"🏠 <b>Menu Utama</b>\nHero: <b>{hero['name']}</b> (Lv.{hero['level']})",
        reply_markup=main_menu_kb()
    )

@router.callback_query(F.data.startswith("menu_"))
async def menu_callback(cb: CallbackQuery):
    menu = cb.data.replace("menu_", "")
    commands = {
        "hero": "/hero",
        "dungeon": "/dungeon",
        "guild": "/guild",
        "market": "/market",
        "shop": "/shop",
        "leaderboard": "/top",
        "marriage": "/marry",
        "daily": "/daily",
    }
    cmd = commands.get(menu)
    if cmd:
        await cb.answer(f"Gunakan command {cmd}")
        await cb.message.answer(f"Gunakan command <b>{cmd}</b>")
