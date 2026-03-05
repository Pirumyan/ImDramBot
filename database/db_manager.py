import asyncpg
from datetime import datetime
from config import DATABASE_URL

async def get_connection():
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL is not set in environment variables")
    return await asyncpg.connect(DATABASE_URL, ssl='require', statement_cache_size=0)

async def init_db():
    conn = await get_connection()
    try:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                streak_count INTEGER DEFAULT 0,
                last_entry_date DATE
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                amount REAL,
                category TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
    finally:
        await conn.close()

async def add_user(user_id, username):
    conn = await get_connection()
    try:
        await conn.execute(
            'INSERT INTO users (user_id, username) VALUES ($1, $2) ON CONFLICT (user_id) DO NOTHING',
            user_id, username
        )
    finally:
        await conn.close()

async def update_streak(user_id):
    conn = await get_connection()
    try:
        today = datetime.now().date()
        row = await conn.fetchrow('SELECT last_entry_date, streak_count FROM users WHERE user_id = $1', user_id)
        if row:
            last_date, streak = row['last_entry_date'], row['streak_count']
            if last_date:
                if last_date == today:
                    return streak
                elif (today - last_date).days == 1:
                    streak += 1
                else:
                    streak = 1
            else:
                streak = 1
            
            await conn.execute(
                'UPDATE users SET streak_count = $1, last_entry_date = $2 WHERE user_id = $3',
                streak, today, user_id
            )
            return streak
    finally:
        await conn.close()
    return 0

async def add_expense(user_id, amount, category):
    # Ensure user exists (especially important after DB migration)
    # We don't have the username here, so we'll use a placeholder or None
    await add_user(user_id, "User")
    
    conn = await get_connection()
    try:
        await conn.execute(
            'INSERT INTO expenses (user_id, amount, category) VALUES ($1, $2, $3)',
            user_id, amount, category
        )
    finally:
        await conn.close()
    return await update_streak(user_id)

async def get_monthly_expenses(user_id, year, month):
    conn = await get_connection()
    try:
        month_str = f"{year}-{month:02d}"
        rows = await conn.fetch(
            '''SELECT category, SUM(amount) as total FROM expenses 
               WHERE user_id = $1 AND to_char(created_at, 'YYYY-MM') = $2
               GROUP BY category''',
            user_id, month_str
        )
        return [(r['category'], r['total']) for r in rows]
    finally:
        await conn.close()

async def get_total_per_period(user_id, year, month):
    conn = await get_connection()
    try:
        month_str = f"{year}-{month:02d}"
        row = await conn.fetchrow(
            '''SELECT SUM(amount) FROM expenses 
               WHERE user_id = $1 AND to_char(created_at, 'YYYY-MM') = $2''',
            user_id, month_str
        )
        return row[0] if row and row[0] else 0
    finally:
        await conn.close()

async def get_recent_expenses(user_id, limit=10):
    conn = await get_connection()
    try:
        rows = await conn.fetch(
            '''SELECT id, amount, category, created_at FROM expenses 
               WHERE user_id = $1 
               ORDER BY created_at DESC 
               LIMIT $2''',
            user_id, limit
        )
        return [(r['id'], r['amount'], r['category'], r['created_at'].strftime("%Y-%m-%d %H:%M:%S")) for r in rows]
    finally:
        await conn.close()

async def delete_expense(expense_id, user_id):
    conn = await get_connection()
    try:
        await conn.execute(
            'DELETE FROM expenses WHERE id = $1 AND user_id = $2',
            expense_id, user_id
        )
    finally:
        await conn.close()

async def get_user_count():
    conn = await get_connection()
    try:
        row = await conn.fetchrow('SELECT COUNT(*) FROM users')
        return row[0] if row else 0
    finally:
        await conn.close()
