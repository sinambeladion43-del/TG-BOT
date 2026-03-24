import asyncpg
import os
import logging

logger = logging.getLogger(__name__)
_pool: asyncpg.Pool = None

async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"), min_size=2, max_size=10)
    return _pool

async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id BIGINT PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            is_banned BOOLEAN DEFAULT FALSE,
            ban_reason TEXT,
            referral_by BIGINT,
            referral_count INT DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            last_active TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS heroes (
            id SERIAL PRIMARY KEY,
            user_id BIGINT UNIQUE REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            hero_class TEXT DEFAULT 'warrior',
            level INT DEFAULT 1,
            exp INT DEFAULT 0,
            hp INT DEFAULT 100,
            max_hp INT DEFAULT 100,
            atk INT DEFAULT 10,
            def INT DEFAULT 5,
            spd INT DEFAULT 5,
            gold INT DEFAULT 500,
            gems INT DEFAULT 0,
            guild_id INT,
            photo_id TEXT,
            title TEXT DEFAULT 'Petualang Baru',
            wins INT DEFAULT 0,
            losses INT DEFAULT 0,
            dungeons_done INT DEFAULT 0,
            total_damage INT DEFAULT 0,
            talent_points INT DEFAULT 0,
            talent_path TEXT DEFAULT 'none',
            married_to BIGINT DEFAULT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS guilds (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            description TEXT DEFAULT 'Tidak ada deskripsi.',
            leader_id BIGINT REFERENCES users(id),
            level INT DEFAULT 1,
            exp INT DEFAULT 0,
            total_power INT DEFAULT 0,
            wins INT DEFAULT 0,
            losses INT DEFAULT 0,
            max_members INT DEFAULT 30,
            is_premium BOOLEAN DEFAULT FALSE,
            premium_until TIMESTAMPTZ,
            photo_id TEXT,
            alliance_with INT,
            announcement TEXT DEFAULT '',
            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS items (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            item_type TEXT NOT NULL,
            rarity TEXT DEFAULT 'common',
            atk_bonus INT DEFAULT 0,
            def_bonus INT DEFAULT 0,
            hp_bonus INT DEFAULT 0,
            spd_bonus INT DEFAULT 0,
            price INT DEFAULT 0,
            description TEXT DEFAULT '',
            photo_id TEXT,
            is_available BOOLEAN DEFAULT TRUE
        );

        CREATE TABLE IF NOT EXISTS hero_items (
            id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
            item_id INT REFERENCES items(id),
            quantity INT DEFAULT 1,
            equipped BOOLEAN DEFAULT FALSE
        );

        CREATE TABLE IF NOT EXISTS weapons (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            rarity TEXT DEFAULT 'common',
            atk_bonus INT DEFAULT 0,
            def_bonus INT DEFAULT 0,
            spd_bonus INT DEFAULT 0,
            price INT DEFAULT 0,
            description TEXT DEFAULT '',
            photo_id TEXT,
            is_available BOOLEAN DEFAULT TRUE
        );

        CREATE TABLE IF NOT EXISTS hero_weapons (
            id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
            weapon_id INT REFERENCES weapons(id),
            equipped BOOLEAN DEFAULT FALSE
        );

        CREATE TABLE IF NOT EXISTS dungeons (
            id SERIAL PRIMARY KEY,
            key TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            enemy_name TEXT DEFAULT 'Monster',
            enemy_hp INT DEFAULT 100,
            enemy_atk INT DEFAULT 10,
            min_level INT DEFAULT 1,
            exp_reward INT DEFAULT 30,
            gold_reward INT DEFAULT 20,
            photo_id TEXT
        );

        CREATE TABLE IF NOT EXISTS cooldowns (
            user_id BIGINT,
            action TEXT,
            expires_at TIMESTAMPTZ,
            PRIMARY KEY (user_id, action)
        );

        CREATE TABLE IF NOT EXISTS guild_wars (
            id SERIAL PRIMARY KEY,
            guild_a INT REFERENCES guilds(id),
            guild_b INT REFERENCES guilds(id),
            score_a INT DEFAULT 0,
            score_b INT DEFAULT 0,
            winner_id INT REFERENCES guilds(id),
            status TEXT DEFAULT 'pending',
            started_at TIMESTAMPTZ DEFAULT NOW(),
            ended_at TIMESTAMPTZ
        );

        CREATE TABLE IF NOT EXISTS market_listings (
            id SERIAL PRIMARY KEY,
            seller_id BIGINT REFERENCES users(id),
            item_id INT,
            item_type TEXT,
            price INT NOT NULL,
            quantity INT DEFAULT 1,
            listed_at TIMESTAMPTZ DEFAULT NOW(),
            is_sold BOOLEAN DEFAULT FALSE
        );

        CREATE TABLE IF NOT EXISTS marriages (
            id SERIAL PRIMARY KEY,
            user_a BIGINT REFERENCES users(id),
            user_b BIGINT REFERENCES users(id),
            married_at TIMESTAMPTZ DEFAULT NOW(),
            anniversary INT DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS daily_logs (
            user_id BIGINT PRIMARY KEY REFERENCES users(id),
            last_daily DATE,
            streak INT DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS admin_logs (
            id SERIAL PRIMARY KEY,
            admin_id BIGINT,
            action TEXT,
            target TEXT,
            detail TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS world_boss (
            id SERIAL PRIMARY KEY,
            name TEXT DEFAULT 'Dragon Raksasa',
            max_hp BIGINT DEFAULT 1000000,
            current_hp BIGINT DEFAULT 1000000,
            is_active BOOLEAN DEFAULT FALSE,
            photo_id TEXT,
            started_at TIMESTAMPTZ,
            ended_at TIMESTAMPTZ
        );

        CREATE TABLE IF NOT EXISTS boss_damage (
            user_id BIGINT REFERENCES users(id),
            boss_id INT REFERENCES world_boss(id),
            damage BIGINT DEFAULT 0,
            PRIMARY KEY (user_id, boss_id)
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        INSERT INTO settings (key, value) VALUES
            ('maintenance', 'false'),
            ('double_exp', 'false'),
            ('double_exp_until', ''),
            ('double_gold', 'false')
        ON CONFLICT (key) DO NOTHING;
        """)

        # Seed default dungeons
        await conn.execute("""
        INSERT INTO dungeons (key, name, description, enemy_name, enemy_hp, enemy_atk, min_level, exp_reward, gold_reward)
        VALUES
            ('forest', 'Hutan Terlarang', 'Hutan gelap penuh monster kayu.', 'Goblin Hutan', 80, 8, 1, 30, 15),
            ('cave', 'Gua Kristal', 'Gua dengan monster berbahaya.', 'Troll Gua', 150, 15, 5, 60, 30),
            ('volcano', 'Gunung Api', 'Lokasi panas dan mematikan.', 'Elemental Api', 280, 28, 10, 110, 55),
            ('abyss', 'Jurang Abadi', 'Kedalaman yang tidak berujung.', 'Demon Jurang', 500, 45, 20, 200, 100),
            ('dragon', 'Sarang Naga', 'Lair sang naga kuno.', 'Naga Kuno', 900, 70, 30, 350, 180)
        ON CONFLICT (key) DO NOTHING;
        """)

        # Seed default items
        await conn.execute("""
        INSERT INTO items (name, item_type, rarity, hp_bonus, atk_bonus, def_bonus, price, description)
        VALUES
            ('Ramuan HP Kecil', 'potion', 'common', 50, 0, 0, 50, 'Pulihkan 50 HP'),
            ('Ramuan HP Besar', 'potion', 'rare', 200, 0, 0, 150, 'Pulihkan 200 HP'),
            ('Jimat Keberanian', 'accessory', 'uncommon', 20, 5, 0, 300, '+5 ATK +20 HP'),
            ('Cincin Perlindungan', 'accessory', 'rare', 0, 0, 10, 500, '+10 DEF'),
            ('Baju Besi Dasar', 'armor', 'common', 0, 0, 8, 200, '+8 DEF'),
            ('Baju Ksatria', 'armor', 'rare', 30, 0, 20, 800, '+20 DEF +30 HP'),
            ('Jubah Mage', 'armor', 'rare', 0, 15, 5, 750, '+15 ATK +5 DEF'),
            ('Sepatu Angin', 'boots', 'uncommon', 0, 0, 0, 400, '+8 SPD')
        ON CONFLICT DO NOTHING;
        """)

        # Seed default weapons
        await conn.execute("""
        INSERT INTO weapons (name, rarity, atk_bonus, def_bonus, spd_bonus, price, description)
        VALUES
            ('Pedang Kayu', 'common', 5, 0, 0, 100, 'Senjata pemula'),
            ('Pedang Besi', 'uncommon', 12, 0, 0, 300, 'Senjata standar'),
            ('Kapak Berdarah', 'rare', 22, 0, -2, 700, 'Tinggi ATK, kurangi SPD'),
            ('Tongkat Sihir', 'uncommon', 15, 0, 3, 400, 'Cocok untuk Mage'),
            ('Busur Elven', 'rare', 18, 0, 8, 650, 'Cocok untuk Archer'),
            ('Pedang Legenda', 'epic', 40, 5, 5, 2000, 'Senjata para ksatria legendaris'),
            ('Tongkat Naga', 'legendary', 60, 0, 10, 5000, 'Dibuat dari tulang naga kuno')
        ON CONFLICT DO NOTHING;
        """)

    logger.info("Database initialized.")

async def fetchone(query, *args):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, *args)

async def fetchall(query, *args):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(query, *args)

async def fetchval(query, *args):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(query, *args)

async def execute(query, *args):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)
