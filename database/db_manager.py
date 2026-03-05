import aiosqlite
from datetime import datetime
from config import DB_PATH

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                streak_count INTEGER DEFAULT 0,
                last_entry_date DATE
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id BIGINT,
                amount REAL,
                category TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        await db.commit()

async def add_user(user_id, username):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)',
            (user_id, username)
        )
        await db.commit()

async def update_streak(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        today = datetime.now().date()
        async with db.execute('SELECT last_entry_date, streak_count FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                last_date_str, streak = row
                if last_date_str:
                    last_date = datetime.strptime(last_date_str, '%Y-%m-%d').date()
                    if last_date == today:
                        return streak
                    elif (today - last_date).days == 1:
                        streak += 1
                    else:
                        streak = 1
                else:
                    streak = 1
                
                await db.execute(
                    'UPDATE users SET streak_count = ?, last_entry_date = ? WHERE user_id = ?',
                    (streak, today.isoformat(), user_id)
                )
                await db.commit()
                return streak
    return 0

async def add_expense(user_id, amount, category):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'INSERT INTO expenses (user_id, amount, category) VALUES (?, ?, ?)',
            (user_id, amount, category)
        )
        await db.commit()
        return await update_streak(user_id)

async def get_monthly_expenses(user_id, year, month):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            '''SELECT category, SUM(amount) FROM expenses 
               WHERE user_id = ? AND strftime("%Y-%m", created_at) = ?
               GROUP BY category''',
            (user_id, f"{year}-{month:02d}")
        ) as cursor:
            return await cursor.fetchall()

async def get_total_per_period(user_id, year, month):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            '''SELECT SUM(amount) FROM expenses 
               WHERE user_id = ? AND strftime("%Y-%m", created_at) = ?''',
            (user_id, f"{year}-{month:02d}")
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row[0] else 0
