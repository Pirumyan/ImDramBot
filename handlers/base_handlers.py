from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from database import db_manager
from config import CATEGORIES
from logic.analyzer import analyze_expenses
from utils.charts import generate_pie_chart
from datetime import datetime
import random

router = Router()

class ExpenseState(StatesGroup):
    waiting_for_amount = State()

SUPPORT_MESSAGES = [
    "Молодец, что внес расходы! 👏",
    "Каждый драм под контролем. Отличная привычка! 💪",
    "Твой кошелек говорит тебе спасибо! 😊",
    "Порядок в финансах — порядок в жизни. Так держать! 🎯"
]

def get_main_menu():
    builder = ReplyKeyboardBuilder()
    builder.button(text="💰 Добавить расход")
    builder.button(text="📊 Статистика")
    builder.button(text="📜 История")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await db_manager.add_user(message.from_user.id, message.from_user.username)
    await message.answer(
        "👋 Привет! Я твой AI-финансовый помощник **ImDram**.\n\n"
        "Я помогу тебе контролировать расходы в Армении 🇦🇲\n\n"
        "Выбери действие снизу или просто отправь мне сумму (например: `5000`)",
        reply_markup=get_main_menu()
    )

@router.message(F.text == "💰 Добавить расход")
async def ask_amount(message: types.Message, state: FSMContext):
    await message.answer("Введи сумму расхода (только цифры):")
    await state.set_state(ExpenseState.waiting_for_amount)

@router.message(ExpenseState.waiting_for_amount, F.text.regexp(r'^\d+$'))
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
    
    if not amount:
        await callback.answer("Ошибка: сумма не найдена.", show_alert=True)
        return

    streak = await db_manager.add_expense(callback.from_user.id, amount, category)
    
    msg = f"✅ Записано: **{int(amount):,} AMD** в категорию **{category}**.\n\n"
    msg += f"{random.choice(SUPPORT_MESSAGES)}\n"
    
    if streak > 1:
        msg += f"🔥 У тебя страйк: **{streak} дней** подряд!"
    
    await callback.message.edit_text(msg)
    await state.clear()
    await callback.answer()

@router.message(F.text == "📊 Статистика")
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

@router.message(F.text == "📜 История")
@router.message(Command("history"))
async def cmd_history(message: types.Message):
    expenses = await db_manager.get_recent_expenses(message.from_user.id)
    
    if not expenses:
        await message.answer("История расходов пуста.")
        return
    
    await message.answer("📜 **Последние траты:**\n(Нажми ❌ под записью, чтобы удалить её)")
    
    for exp_id, amount, category, date_str in expenses:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        date_fmt = date_obj.strftime("%d.%m %H:%M")
        
        builder = InlineKeyboardBuilder()
        builder.button(text=f"❌ Удалить {int(amount):,} AMD", callback_data=f"del_{exp_id}")
        
        text = f"🔹 {date_fmt} — **{int(amount):,} AMD** ({category})"
        await message.answer(text, reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("del_"))
async def process_delete(callback: types.CallbackQuery):
    expense_id = int(callback.data.split("_")[1])
    await db_manager.delete_expense(expense_id, callback.from_user.id)
    
    await callback.message.edit_text("🗑 Запись удалена.")
    await callback.answer("Удалено")
