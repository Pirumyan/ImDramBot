from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from database import db_manager
from config import CATEGORIES, INCOME_CATEGORIES, ADMIN_ID
from logic.analyzer import analyze_expenses
from logic.currency import convert_to_amd
from utils.charts import generate_pie_chart
from logic.ai_parser import parse_expense_text
from utils.locales import get_msg
from datetime import datetime
import random

router = Router()

class ExpenseState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_income = State()

SUPPORT_MESSAGES = [
    "Молодец! 👏",
    "Каждый драм под контролем. Отличная привычка! 💪",
    "Твой кошелек говорит тебе спасибо! 😊",
    "Порядок в финансах — порядок в жизни. Так держать! 🎯"
]

def get_main_menu(lang):
    builder = ReplyKeyboardBuilder()
    builder.button(text=get_msg(lang, "btn_expense"))
    builder.button(text=get_msg(lang, "btn_income"))
    builder.button(text=get_msg(lang, "btn_stats"))
    builder.button(text=get_msg(lang, "btn_history"))
    builder.button(text=get_msg(lang, "btn_lang"))
    builder.adjust(2, 2, 1)
    return builder.as_markup(resize_keyboard=True)

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await db_manager.add_user(message.from_user.id, message.from_user.username)
    lang = await db_manager.get_user_language(message.from_user.id)
    await message.answer(
        get_msg(lang, "start"),
        reply_markup=get_main_menu(lang)
    )

@router.message(lambda msg: msg.text in [get_msg("ru", "btn_lang"), get_msg("en", "btn_lang"), get_msg("hy", "btn_lang")])
@router.message(Command("lang"))
async def cmd_lang(message: types.Message):
    lang = await db_manager.get_user_language(message.from_user.id)
    builder = InlineKeyboardBuilder()
    builder.button(text="🇷🇺 Русский", callback_data="lang_ru")
    builder.button(text="🇺🇸 English", callback_data="lang_en")
    builder.button(text="🇦🇲 Հայերեն", callback_data="lang_hy")
    builder.adjust(1)
    await message.answer(get_msg(lang, "lang_prompt"), reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("lang_"))
async def process_lang(callback: types.CallbackQuery):
    lang_code = callback.data.split("_")[1]
    await db_manager.set_user_language(callback.from_user.id, lang_code)
    await callback.message.edit_text(get_msg(lang_code, "lang_changed"))
    await callback.message.answer(get_msg(lang_code, "start"), reply_markup=get_main_menu(lang_code))

@router.message(lambda msg: msg.text in [get_msg("ru", "btn_expense"), get_msg("en", "btn_expense"), get_msg("hy", "btn_expense")])
async def ask_amount(message: types.Message, state: FSMContext):
    lang = await db_manager.get_user_language(message.from_user.id)
    await message.answer(get_msg(lang, "ask_amount"))
    await state.set_state(ExpenseState.waiting_for_amount)

@router.message(lambda msg: msg.text in [get_msg("ru", "btn_income"), get_msg("en", "btn_income"), get_msg("hy", "btn_income")])
async def ask_income(message: types.Message, state: FSMContext):
    lang = await db_manager.get_user_language(message.from_user.id)
    await message.answer(get_msg(lang, "ask_income"))
    await state.set_state(ExpenseState.waiting_for_income)

@router.message(lambda msg: msg.text in [get_msg("ru", "btn_stats"), get_msg("en", "btn_stats"), get_msg("hy", "btn_stats")] or msg.text == "/stats")
async def cmd_stats(message: types.Message):
    lang = await db_manager.get_user_language(message.from_user.id)
    now = datetime.now()
    category_sums = await db_manager.get_monthly_expenses(message.from_user.id, now.year, now.month)
    total_spent, total_income = await db_manager.get_total_per_period(message.from_user.id, now.year, now.month)
    
    if total_spent == 0 and total_income == 0:
        await message.answer(get_msg(lang, "stats_empty"))
        return
    
    msg = get_msg(lang, "stats_header", period=now.strftime('%B %Y'))
    msg += get_msg(lang, "stats_income", amount=f"{int(total_income):,}")
    msg += get_msg(lang, "stats_expense", amount=f"{int(total_spent):,}")
    
    balance = total_income - total_spent
    msg += get_msg(lang, "stats_balance", amount=f"{int(balance):,}")
    
    analysis = analyze_expenses(total_spent, category_sums)
    if total_spent > 0:
        msg += "\n".join(analysis["report_lines"])
        
        forecast_msg = get_msg(lang, "forecast", amount=f"{analysis['forecast']:,}")
        msg += f"\n\n{forecast_msg}"
        
        if analysis["advice"]:
            savings_msg = get_msg(lang, "savings", amount=f"{analysis['potential_yearly_savings']:,}")
            msg += "\n\n💡 " + "\n".join(analysis["advice"])
            msg += f"\n\n{savings_msg}"
    
    if total_spent > 0:
        chart_buf = generate_pie_chart(category_sums, total_spent)
        photo = types.BufferedInputFile(chart_buf.read(), filename="chart.png")
        await message.answer_photo(photo, caption=msg, parse_mode="Markdown")
    else:
        await message.answer(msg, parse_mode="Markdown")

@router.message(lambda msg: msg.text in [get_msg("ru", "btn_history"), get_msg("en", "btn_history"), get_msg("hy", "btn_history")] or msg.text == "/history")
async def cmd_history(message: types.Message):
    lang = await db_manager.get_user_language(message.from_user.id)
    recent = await db_manager.get_recent_transactions(message.from_user.id)
    
    if not recent:
        await message.answer(get_msg(lang, "history_empty"))
        return
    
    await message.answer(get_msg(lang, "history_header"))
    
    for item_id, amount, cat, date_str, type_str in recent:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        date_fmt = date_obj.strftime("%d.%m %H:%M")
        
        builder = InlineKeyboardBuilder()
        builder.button(text=f"❌ Удалить", callback_data=f"del_{type_str}_{item_id}")
        
        emoji = "🔴" if type_str == "expense" else "🟢"
        text = f"{emoji} {date_fmt} — **{int(amount):,} AMD** ({cat})"
        await message.answer(text, reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("del_"))
async def process_delete(callback: types.CallbackQuery):
    _, type_str, item_id = callback.data.split("_")
    await db_manager.delete_transaction(int(item_id), callback.from_user.id, type_str)
    
    lang = await db_manager.get_user_language(callback.from_user.id)
    await callback.message.edit_text(get_msg(lang, "deleted"))
    await callback.answer()

@router.message(Command("admin_stats"))
async def cmd_admin_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    count = await db_manager.get_user_count()
    await message.answer(f"📊 **Админ-статистика:**\n\nВсего пользователей в базе: **{count}**")

@router.callback_query(F.data.startswith("cat_"))
async def process_category(callback: types.CallbackQuery, state: FSMContext):
    cat_id = callback.data.split("_")[1]
    
    # Check if category is expense or income by searching dicts
    category = "Unknown"
    is_income = False
    
    if cat_id in CATEGORIES.values():
        category = cat_id
    elif cat_id in INCOME_CATEGORIES.values():
        category = cat_id
        is_income = True
        
    data = await state.get_data()
    amount = data.get("amount", 0)
    
    lang = await db_manager.get_user_language(callback.from_user.id)
    
    if not amount:
        await callback.answer(get_msg(lang, "err_sum"), show_alert=True)
        return

    if is_income:
        streak = await db_manager.add_income(callback.from_user.id, amount, category)
        msg = get_msg(lang, "saved_income", amount=f"{int(amount):,}", category=category)
    else:
        streak = await db_manager.add_expense(callback.from_user.id, amount, category)
        msg = get_msg(lang, "saved_expense", amount=f"{int(amount):,}", category=category)
    
    if streak > 1:
        msg += "\n" + random.choice(SUPPORT_MESSAGES) + "\n"
        msg += get_msg(lang, "strike", strike=streak)
    
    await callback.message.edit_text(msg)
    await state.clear()
    await callback.answer()

@router.message(ExpenseState.waiting_for_amount)
@router.message(ExpenseState.waiting_for_income)
@router.message(F.text & ~F.text.startswith("/"))
async def process_text_or_amount(message: types.Message, state: FSMContext):
    lang = await db_manager.get_user_language(message.from_user.id)
    
    # Ignore keyboard button messages
    ignore_texts = [
        get_msg(l, btn) for l in ["ru", "en", "hy"] 
        for btn in ["btn_expense", "btn_income", "btn_stats", "btn_history", "btn_lang"]
    ]
    if message.text in ignore_texts:
        return
        
    wait_msg = await message.answer(get_msg(lang, "thinking"))
    
    current_state = await state.get_state()
    forced_type = None
    if current_state == ExpenseState.waiting_for_income.state:
        forced_type = "income"
    elif current_state == ExpenseState.waiting_for_amount.state:
        forced_type = "expense"
    
    if message.text.isdigit() or (message.text.replace('.', '', 1).isdigit() and message.text.count('.') < 2):
        amount = float(message.text)
        await state.update_data(amount=amount)
        
        builder = InlineKeyboardBuilder()
        dicts = INCOME_CATEGORIES if forced_type == "income" else CATEGORIES
        
        for key, name in dicts.items():
            builder.button(text=name, callback_data=f"cat_{name}")
        builder.adjust(2)
        
        await wait_msg.edit_text(get_msg(lang, "choose_cat"), reply_markup=builder.as_markup())
        return

    # Use Gemini
    parsed = await parse_expense_text(message.text)
    
    amount = parsed.get("amount")
    category = parsed.get("category")
    parsed_type = parsed.get("type", "expense")
    currency = parsed.get("currency", "AMD")
    
    if forced_type:
        parsed_type = forced_type
    
    if not amount:
        await wait_msg.edit_text(get_msg(lang, "not_understood"))
        return
        
    # Convert currency if needed
    if currency != "AMD":
        amount = await convert_to_amd(amount, currency)
        
    dicts = INCOME_CATEGORIES if parsed_type == "income" else CATEGORIES
        
    if category and category in dicts.values():
        if parsed_type == "income":
            streak = await db_manager.add_income(message.from_user.id, amount, category)
            msg = get_msg(lang, "saved_income", amount=f"{int(amount):,}", category=category)
        else:
            streak = await db_manager.add_expense(message.from_user.id, amount, category)
            msg = get_msg(lang, "saved_expense", amount=f"{int(amount):,}", category=category)
            
        if streak > 1:
            msg += "\n" + random.choice(SUPPORT_MESSAGES) + "\n"
            msg += get_msg(lang, "strike", strike=streak)
        await wait_msg.edit_text(msg)
        await state.clear()
    else:
        # Ask for category
        await state.update_data(amount=amount)
        builder = InlineKeyboardBuilder()
        for key, name in dicts.items():
            builder.button(text=name, callback_data=f"cat_{name}")
        builder.adjust(2)
        await wait_msg.edit_text(f"{amount} AMD. " + get_msg(lang, "choose_cat"), reply_markup=builder.as_markup())
