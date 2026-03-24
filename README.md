# 🎮 RPG Kingdom — Telegram Bot Game

Bot game RPG lengkap dengan Hero, Dungeon, Guild War, Market, Nikah, dan banyak lagi!

---

## ⚡ Fitur Lengkap

### Gameplay
- ⚔️ 3 kelas hero: Warrior, Mage, Archer
- 🏰 5 dungeon dengan sistem battle animasi
- 🎁 Loot system dengan rarity (common → legendary)
- 🌳 Talent tree per kelas hero
- 🐉 World boss event
- ⚔️ Sistem duel PvP antar pemain

### Sosial & Guild
- 👥 Guild system lengkap (buat, join, kick, announcement)
- ⚔️ Guild War mingguan
- 🤝 Aliansi antar guild
- 💑 Sistem pernikahan dengan bonus EXP
- 🔗 Referral system

### Ekonomi
- 🏪 Market player-to-player
- 🛍️ Toko item & senjata
- 🌅 Daily login reward dengan streak
- 💰 Gold & Gems economy

### Admin
- 🛡️ Panel admin lengkap (/admin)
- 🖼️ Set foto untuk item, senjata, dungeon, guild, boss, hero
- 📢 Broadcast ke semua user
- 🚫 Ban/Unban pemain
- 🎁 Give/Take resource
- 🔧 Mode maintenance
- 🐉 Spawn world boss manual
- ⭐ Toggle double EXP/Gold event
- 📊 Statistik real-time
- 📋 Admin action log

---

## 🚀 Setup & Deploy

### 1. Clone & Konfigurasi

```bash
git clone https://github.com/username/repo.git
cd repo
cp .env.example .env
```

Edit file `.env`:
```
BOT_TOKEN=token_dari_botfather
DATABASE_URL=postgresql://...
ADMIN_IDS=your_telegram_id
LOG_CHANNEL_ID=-100xxx  # opsional
```

### 2. Deploy ke Railway

1. Push ke GitHub
2. Buka [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Tambahkan service **PostgreSQL** dari Railway
4. Set environment variables:
   - `BOT_TOKEN`
   - `DATABASE_URL` (copy dari PostgreSQL service Railway)
   - `ADMIN_IDS`
   - `LOG_CHANNEL_ID` (opsional)
5. Deploy otomatis!

### 3. Local Development

```bash
pip install -r requirements.txt
python bot.py
```

---

## 🖼️ Cara Set Foto (Admin)

1. Kirim foto ke bot
2. **Reply** foto tersebut dengan command:

| Command | Keterangan |
|---|---|
| `/setphoto hero [user_id]` | Foto hero pemain |
| `/setphoto item [id]` | Foto item |
| `/setphoto weapon [id]` | Foto senjata |
| `/setphoto dungeon [key]` | Foto dungeon (forest/cave/volcano/abyss/dragon) |
| `/setphoto guild [id]` | Foto guild |
| `/setphoto boss` | Foto world boss aktif |

Lihat ID item/weapon/dungeon dengan: `/admin` → Set Photo → List Item/Weapon/Dungeon

---

## 📋 Daftar Command Pemain

| Command | Fungsi |
|---|---|
| `/start` | Mulai & buat hero |
| `/hero` atau `/me` | Lihat stats hero |
| `/dungeon` atau `/d` | Masuk dungeon |
| `/guild` atau `/g` | Info & kelola guild |
| `/war` | Guild war |
| `/market` atau `/pasar` | Market antar pemain |
| `/shop` atau `/toko` | Toko resmi |
| `/top` atau `/lb` | Leaderboard global |
| `/marry @username` | Lamar pemain |
| `/duel @username` | Tantang duel |
| `/daily` | Klaim reward harian |
| `/boss` | Serang world boss |
| `/joinguild [id]` | Bergabung guild |

## 📋 Daftar Command Admin

| Command | Fungsi |
|---|---|
| `/admin` | Panel admin utama |
| `/ban [id] [alasan]` | Ban user |
| `/unban [id]` | Unban user |
| `/banlist` | Daftar banned |
| `/give [id] [field] [jumlah]` | Beri resource |
| `/take [id] [field] [jumlah]` | Ambil resource |
| `/userinfo [id]` | Info lengkap user |
| `/resetcd [id]` | Reset cooldown |
| `/forcewar [id_a] [id_b]` | Paksa guild war |
| `/setphoto [tipe] [id]` | Set foto (reply foto) |
| `/adminhelp` | Bantuan command admin |

---

## 🗄️ Database

PostgreSQL dengan tabel:
`users`, `heroes`, `guilds`, `items`, `hero_items`, `weapons`, `hero_weapons`,
`dungeons`, `cooldowns`, `guild_wars`, `market_listings`, `marriages`,
`daily_logs`, `admin_logs`, `world_boss`, `boss_damage`, `settings`

Semua tabel dibuat otomatis saat bot pertama kali jalan.
Default item, senjata, dan dungeon juga di-seed otomatis.
