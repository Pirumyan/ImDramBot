import asyncpg
from datetime import datetime
from config import DATABASE_URL
import logging

pool = None

async def init_pool():
    global pool
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL is not set in environment variables")
    pool = await asyncpg.create_pool(DATABASE_URL, ssl='require', statement_cache_size=0, min_size=1, max_size=10)

async def close_pool():
    global pool
    if pool:
        await pool.close()

async def init_db():
    if pool is None:
        await init_pool()
        
    async with pool.acquire() as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                streak_count INTEGER DEFAULT 0,
                last_entry_date DATE
            )
        ''')
        try:
            await conn.execute('ALTER TABLE users ADD COLUMN language VARCHAR(10) DEFAULT \'ru\'')
        except asyncpg.exceptions.DuplicateColumnError:
            pass

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
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS incomes (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                amount REAL,
                source TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')

async def add_user(user_id, username, lang='ru'):
    async with pool.acquire() as conn:
        await conn.execute(
            'INSERT INTO users (user_id, username, language) VALUES ($1, $2, $3) ON CONFLICT (user_id) DO NOTHING',
            user_id, username, lang
        )

async def get_user_language(user_id):
    async with pool.acquire() as conn:
        row = await conn.fetchrow('SELECT language FROM users WHERE user_id = $1', user_id)
        return row['language'] if row and 'language' in row else 'ru'

async def set_user_language(user_id, lang):
    async with pool.acquire() as conn:
        await conn.execute('UPDATE users SET language = $1 WHERE user_id = $2', lang, user_id)

async def update_streak(user_id):
    async with pool.acquire() as conn:
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
    return 0

async def add_expense(user_id, amount, category):
    await add_user(user_id, "User")
    async with pool.acquire() as conn:
        await conn.execute(
            'INSERT INTO expenses (user_id, amount, category) VALUES ($1, $2, $3)',
            user_id, amount, category
        )
    return await update_streak(user_id)

async def add_income(user_id, amount, source):
    await add_user(user_id, "User")
    async with pool.acquire() as conn:
        await conn.execute(
            'INSERT INTO incomes (user_id, amount, source) VALUES ($1, $2, $3)',
            user_id, amount, source
        )
    return await update_streak(user_id)

async def get_monthly_expenses(user_id, year, month):
    async with pool.acquire() as conn:
        month_str = f"{year}-{month:02d}"
        rows = await conn.fetch(
            '''SELECT category, SUM(amount) as total FROM expenses 
               WHERE user_id = $1 AND to_char(created_at, 'YYYY-MM') = $2
               GROUP BY category''',
            user_id, month_str
        )
        return [(r['category'], r['total']) for r in rows]

async def get_total_per_period(user_id, year, month):
    async with pool.acquire() as conn:
        month_str = f"{year}-{month:02d}"
        # Total Expenses
        row_exp = await conn.fetchrow(
            '''SELECT SUM(amount) FROM expenses 
               WHERE user_id = $1 AND to_char(created_at, 'YYYY-MM') = $2''',
            user_id, month_str
        )
        exp = row_exp[0] if row_exp and row_exp[0] else 0
        
        # Total Incomes
        row_inc = await conn.fetchrow(
            '''SELECT SUM(amount) FROM incomes 
               WHERE user_id = $1 AND to_char(created_at, 'YYYY-MM') = $2''',
            user_id, month_str
        )
        inc = row_inc[0] if row_inc and row_inc[0] else 0
        
        return exp, inc

async def get_recent_transactions(user_id, limit=10):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            '''
            SELECT id, amount, category as cat, created_at, 'expense' as type FROM expenses WHERE user_id = $1
            UNION ALL
            SELECT id, amount, source as cat, created_at, 'income' as type FROM incomes WHERE user_id = $1
            ORDER BY created_at DESC LIMIT $2
            ''',
            user_id, limit
        )
        return [(r['id'], r['amount'], r['cat'], r['created_at'].strftime("%Y-%m-%d %H:%M:%S"), r['type']) for r in rows]

async def delete_transaction(item_id, user_id, type_str):
    async with pool.acquire() as conn:
        table = 'expenses' if type_str == 'expense' else 'incomes'
        await conn.execute(
            f'DELETE FROM {table} WHERE id = $1 AND user_id = $2',
            item_id, user_id
        )

async def get_user_count():
    async with pool.acquire() as conn:
        row = await conn.fetchrow('SELECT COUNT(*) FROM users')
        return row[0] if row else 0

async def get_all_transactions(user_id):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            '''
            SELECT id, amount, category as cat, created_at, 'expense' as type FROM expenses WHERE user_id = $1
            UNION ALL
            SELECT id, amount, source as cat, created_at, 'income' as type FROM incomes WHERE user_id = $1
            ORDER BY created_at DESC
            ''',
            user_id
        )
        return [(r['id'], r['amount'], r['cat'], r['created_at'].strftime("%Y-%m-%d %H:%M:%S"), r['type']) for r in rows]

async def get_users_to_remind():
    async with pool.acquire() as conn:
        rows = await conn.fetch('SELECT user_id, language FROM users WHERE last_entry_date < CURRENT_DATE OR last_entry_date IS NULL')
        return [(r['user_id'], r['language']) for r in rows]
