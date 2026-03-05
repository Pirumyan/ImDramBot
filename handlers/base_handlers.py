from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import db_manager
from config import CATEGORIES
from logic.analyzer import analyze_expenses
from utils.charts import generate_pie_chart
from datetime import datetime
import random

router = Router()

class ExpenseState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_category = State()

SUPPORT_MESSAGES = [
    "Молодец, что внес расходы! 👏",
    "Каждый драм под контролем. Отличная привычка! 💪",
    "Твой кошелек говорит тебе спасибо! 😊",
    "Порядок в финансах — порядок в жизни. Так держать! 🎯"
]

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await db_manager.add_user(message.from_user.id, message.from_user.username)
    await message.answer(
        "👋 Привет! Я твой AI-финансовый помощник **ImDram**.\n\n"
        "Я помогу тебе контролировать расходы в Армении 🇦🇲\n\n"
        "**Как пользоваться:**\n"
        "1. Просто отправь мне сумму (например: `5000`)\n"
        "2. Выбери категорию\n"
        "3. В конце месяца получи анализ и советы!\n\n"
        "Попробуй прямо сейчас — напиши сумму расхода."
    )

@router.message(F.text.regexp(r'^\d+$'))
async def process_amount(message: types.Message, state: FSMContext):
    amount = float(message.text)
    await state.update_data(amount=amount)
    
    builder = InlineKeyboardBuilder()
    for key, name in CATEGORIES.items():
        builder.button(text=name, callback_data=f"cat_{name}")
    builder.adjust(2)
    
    await message.answer("Выбери категорию для этого расхода:", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("cat_"))
async def process_category(callback: types.CallbackQuery, state: FSMContext):
    category = callback.data.split("_")[1]
    data = await state.get_data()
    amount = data.get("amount")
    
    streak = await db_manager.add_expense(callback.from_user.id, amount, category)
    
    msg = f"✅ Записано: **{int(amount):,} AMD** в категорию **{category}**.\n\n"
    msg += f"{random.choice(SUPPORT_MESSAGES)}\n"
    
    if streak > 1:
        msg += f"🔥 У тебя страйк: **{streak} дней** подряд!"
    
    await callback.message.edit_text(msg)
    await state.clear()
    await callback.answer()

@router.message(Command("stats"))
async def cmd_stats(message: types.Message):
    now = datetime.now()
    category_sums = await db_manager.get_monthly_expenses(message.from_user.id, now.year, now.month)
    total_spent = await db_manager.get_total_per_period(message.from_user.id, now.year, now.month)
    
    if total_spent == 0:
        await message.answer("За этот месяц пока нет расходов. Самое время что-то купить! 😊")
        return
    
    analysis = analyze_expenses(total_spent, category_sums)
    
    msg = f"📊 **Статистика за {now.strftime('%B %Y')}**\n\n"
    msg += f"💰 Всего потрачено: **{int(total_spent):,} AMD**\n\n"
    msg += "\n".join(analysis["report_lines"])
    
    msg += f"\n\n📈 Прогноз до конца месяца: **{analysis['forecast']:,} AMD**"
    
    if analysis["advice"]:
        msg += "\n\n💡 **Советы:**\n" + "\n".join(analysis["advice"])
        msg += f"\n\n🎯 Потенциальная экономия за год: **{analysis['potential_yearly_savings']:,} AMD**"
    
    # Generate chart
    chart_buf = generate_pie_chart(category_sums, total_spent)
    photo = types.BufferedInputFile(chart_buf.read(), filename="chart.png")
    
    await message.answer_photo(photo, caption=msg, parse_mode="Markdown")
