import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

from middlewares.auth import AuthMiddleware
from middlewares.maintenance import MaintenanceMiddleware
from handlers import start, hero, dungeon, guild, war, market, marriage, leaderboard, shop, admin, profile, duel, daily
from services.database import init_db
from services.scheduler import start_scheduler

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

async def main():
    bot = Bot(
        token=os.getenv("BOT_TOKEN"),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Middlewares
    dp.message.middleware(MaintenanceMiddleware())
    dp.callback_query.middleware(MaintenanceMiddleware())
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    # Routers
    dp.include_router(start.router)
    dp.include_router(profile.router)
    dp.include_router(hero.router)
    dp.include_router(dungeon.router)
    dp.include_router(guild.router)
    dp.include_router(war.router)
    dp.include_router(market.router)
    dp.include_router(marriage.router)
    dp.include_router(leaderboard.router)
    dp.include_router(shop.router)
    dp.include_router(duel.router)
    dp.include_router(daily.router)
    dp.include_router(admin.router)

    # Init DB & Scheduler
    await init_db()
    await start_scheduler(bot)

    logger.info("Bot started!")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
