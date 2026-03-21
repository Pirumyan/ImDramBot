from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from database import db_manager
from config import CATEGORIES, INCOME_CATEGORIES, ADMIN_ID
from logic.analyzer import analyze_expenses
from logic.currency import convert_to_amd, get_all_rates
from utils.charts import generate_pie_chart
from logic.ai_parser import parse_expense_text, parse_audio_file
from utils.locales import get_msg, get_category_name
from datetime import datetime
from aiogram import Bot
from aiogram.types import FSInputFile
import random
import os
import csv


router = Router()

class ExpenseState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_income = State()

def get_main_menu(lang):
    builder = ReplyKeyboardBuilder()
    builder.button(text=get_msg(lang, "btn_expense"))
    builder.button(text=get_msg(lang, "btn_income"))
    builder.button(text=get_msg(lang, "btn_stats"))
    builder.button(text=get_msg(lang, "btn_history"))
    builder.button(text=get_msg(lang, "btn_rates"))
    builder.button(text=get_msg(lang, "btn_budget"))
    builder.button(text=get_msg(lang, "btn_export"))
    builder.button(text=get_msg(lang, "btn_lang"))
    builder.adjust(2, 2, 2, 2)
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

@router.message(lambda msg: msg.text in [get_msg("ru", "btn_rates"), get_msg("en", "btn_rates"), get_msg("hy", "btn_rates")] or msg.text == "/rates")
async def cmd_rates(message: types.Message):
    lang = await db_manager.get_user_language(message.from_user.id)
    wait_msg = await message.answer(get_msg(lang, "thinking"))
    rates = await get_all_rates()
    await wait_msg.edit_text(get_msg(lang, "rates_text", usd=rates.get("USD", "—"), eur=rates.get("EUR", "—"), rub=rates.get("RUB", "—")))

def get_stats_keyboard(lang):
    builder = InlineKeyboardBuilder()
    builder.button(text=get_msg(lang, "btn_week"), callback_data="stats_week")
    builder.button(text=get_msg(lang, "btn_month"), callback_data="stats_month")
    builder.button(text=get_msg(lang, "btn_year"), callback_data="stats_year")
    builder.adjust(3)
    return builder.as_markup()

async def send_stats(message_or_call, user_id, lang, period="month"):
    cat_sums, total_spent, total_income = await db_manager.get_stats_by_period(user_id, period)
    
    if total_spent == 0 and total_income == 0:
        msg_text = get_msg(lang, "stats_empty")
        if isinstance(message_or_call, types.Message):
            await message_or_call.answer(msg_text, reply_markup=get_stats_keyboard(lang))
        else:
            await message_or_call.message.edit_text(msg_text, reply_markup=get_stats_keyboard(lang))
        return
    
    period_label = get_msg(lang, "btn_" + period)
    msg = get_msg(lang, "stats_header", period=period_label)
    msg += get_msg(lang, "stats_income", amount=f"{int(total_income):,}")
    msg += get_msg(lang, "stats_expense", amount=f"{int(total_spent):,}")
    balance = total_income - total_spent
    msg += get_msg(lang, "stats_balance", amount=f"{int(balance):,}")
    
    analysis = analyze_expenses(total_spent, cat_sums, lang=lang)
    if total_spent > 0:
        msg += "\n".join(analysis["report_lines"])
        if period == "month":
            forecast_msg = get_msg(lang, "forecast", amount=f"{analysis['forecast']:,}")
            msg += f"\n\n{forecast_msg}"
            
    markup = get_stats_keyboard(lang)
    sent_msg = None
    if isinstance(message_or_call, types.Message):
        if total_spent > 0:
            chart_buf = generate_pie_chart(cat_sums, total_spent, lang)
            photo = types.BufferedInputFile(chart_buf.read(), filename="chart.png")
            sent_msg = await message_or_call.answer_photo(photo, caption=msg, parse_mode="Markdown", reply_markup=markup)
        else:
            sent_msg = await message_or_call.answer(msg, parse_mode="Markdown", reply_markup=markup)
    else:
        # Edit message if no photo is attached, else answer with new photo
        if message_or_call.message.photo and total_spent > 0:
            chart_buf = generate_pie_chart(cat_sums, total_spent, lang)
            photo = types.InputMediaPhoto(media=types.BufferedInputFile(chart_buf.read(), filename="chart.png"), caption=msg, parse_mode="Markdown")
            sent_msg = await message_or_call.message.edit_media(media=photo, reply_markup=markup)
        elif not message_or_call.message.photo and total_spent == 0:
            sent_msg = await message_or_call.message.edit_text(msg, parse_mode="Markdown", reply_markup=markup)
        else:
            # Type changed (photo -> text or text -> photo)
            try:
                await message_or_call.message.delete()
            except:
                pass
            if total_spent > 0:
                chart_buf = generate_pie_chart(cat_sums, total_spent, lang)
                photo = types.BufferedInputFile(chart_buf.read(), filename="chart.png")
                sent_msg = await message_or_call.message.answer_photo(photo, caption=msg, parse_mode="Markdown", reply_markup=markup)
            else:
                sent_msg = await message_or_call.message.answer(msg, parse_mode="Markdown", reply_markup=markup)

    # Background AI task
    if period == "month" and total_spent > 0:
        target_msg = sent_msg if sent_msg else getattr(message_or_call, "message", None)
        if target_msg:
            async def fetch_ai(b_msg, b_text, b_spent, b_sums, b_lang, b_markup):
                from logic.ai_parser import generate_financial_advice
                adv = await generate_financial_advice(b_spent, b_sums, b_lang)
                if adv:
                    new_msg = b_text + f"\n\n🤖 **AI:** {adv}"
                    try:
                        if getattr(b_msg, "photo", None):
                            await b_msg.edit_caption(caption=new_msg, parse_mode="Markdown", reply_markup=b_markup)
                        else:
                            await b_msg.edit_text(new_msg, parse_mode="Markdown", reply_markup=b_markup)
                    except Exception as e:
                        import logging
                        logging.error(f"Error appending AI text: {e}")
            
            import asyncio
            asyncio.create_task(fetch_ai(target_msg, msg, total_spent, cat_sums, lang, markup))

@router.message(lambda msg: msg.text in [get_msg("ru", "btn_stats"), get_msg("en", "btn_stats"), get_msg("hy", "btn_stats")] or msg.text == "/stats")
async def cmd_stats(message: types.Message):
    lang = await db_manager.get_user_language(message.from_user.id)
    await send_stats(message, message.from_user.id, lang, "month")

@router.callback_query(F.data.startswith("stats_"))
async def process_stats(callback: types.CallbackQuery):
    period = callback.data.split("_")[1]
    lang = await db_manager.get_user_language(callback.from_user.id)
    await send_stats(callback, callback.from_user.id, lang, period)
    await callback.answer()

@router.message(Command("budget"))
async def cmd_budget(message: types.Message):
    lang = await db_manager.get_user_language(message.from_user.id)
    parts = message.text.split()
    if len(parts) == 2 and parts[1].isdigit():
        budget = float(parts[1])
        await db_manager.set_user_budget(message.from_user.id, budget)
        await message.answer(get_msg(lang, "budget_set", amount=f"{int(budget):,}"))
    else:
        budget = await db_manager.get_user_budget(message.from_user.id)
        if budget > 0:
            await message.answer(get_msg(lang, "budget_status", amount=f"{int(budget):,}"))
        else:
            await message.answer(get_msg(lang, "budget_empty"))

@router.message(lambda msg: msg.text in [get_msg("ru", "btn_budget"), get_msg("en", "btn_budget"), get_msg("hy", "btn_budget")])
async def btn_budget(message: types.Message):
    await cmd_budget(message)

@router.message(Command("export"))
async def cmd_export(message: types.Message):
    lang = await db_manager.get_user_language(message.from_user.id)
    transactions = await db_manager.get_all_transactions(message.from_user.id)
    
    if not transactions:
        await message.answer(get_msg(lang, "export_empty"))
        return
        
    os.makedirs("temp", exist_ok=True)
    filename = f"temp/export_{message.from_user.id}.csv"
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "Amount", "Category", "Date", "Type"])
        for t in transactions:
            writer.writerow(t)
            
    try:
        doc = FSInputFile(filename)
        await message.answer_document(doc, caption=get_msg(lang, "export_success"))
    finally:
        if os.path.exists(filename):
            os.remove(filename)

@router.message(lambda msg: msg.text in [get_msg("ru", "btn_export"), get_msg("en", "btn_export"), get_msg("hy", "btn_export")])
async def btn_export_msg(message: types.Message):
    await cmd_export(message)


@router.message(lambda msg: msg.text in [get_msg("ru", "btn_history"), get_msg("en", "btn_history"), get_msg("hy", "btn_history")] or msg.text == "/history")
async def cmd_history(message: types.Message):
    lang = await db_manager.get_user_language(message.from_user.id)
    recent = await db_manager.get_recent_transactions(message.from_user.id)
    
    if not recent:
        await message.answer(get_msg(lang, "history_empty"))
        return
    
    await message.answer(get_msg(lang, "history_header"))
    
    for item_id, amount, cat_ru, date_str, type_str in recent:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        date_fmt = date_obj.strftime("%d.%m %H:%M")
        
        cat_translated = get_category_name(cat_ru, lang, is_income=(type_str == "income"))
        
        builder = InlineKeyboardBuilder()
        builder.button(text=get_msg(lang, "del_btn"), callback_data=f"del_{type_str}_{item_id}")
        
        emoji = "🔴" if type_str == "expense" else "🟢"
        text = f"{emoji} {date_fmt} — **{int(amount):,} AMD** ({cat_translated})"
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
    parts = callback.data.split("_")
    if len(parts) >= 3:
        type_str = parts[1]
        cat_id = parts[2]
    else:
        type_str = "expense"
        cat_id = parts[1]
    
    category = "Unknown"
    is_income = (type_str == "income")
    
    if not is_income and cat_id in CATEGORIES:
        category = CATEGORIES[cat_id]
    elif is_income and cat_id in INCOME_CATEGORIES:
        category = INCOME_CATEGORIES[cat_id]
        
    data = await state.get_data()
    amount = data.get("amount", 0)
    
    lang = await db_manager.get_user_language(callback.from_user.id)
    
    if not amount:
        await callback.answer(get_msg(lang, "err_sum"), show_alert=True)
        return

    ui_category = get_category_name(cat_id, lang, is_income=is_income)

    if is_income:
        streak = await db_manager.add_income(callback.from_user.id, amount, category)
        msg = get_msg(lang, "saved_income", amount=f"{int(amount):,}", category=ui_category)
    else:
        streak = await db_manager.add_expense(callback.from_user.id, amount, category, None)
        msg = get_msg(lang, "saved_expense", amount=f"{int(amount):,}", category=ui_category)
        
        # Budget check
        budget = await db_manager.get_user_budget(callback.from_user.id)
        if budget > 0:
            _, t_spent, _ = await db_manager.get_stats_by_period(callback.from_user.id, "month")
            if t_spent > budget:
                msg += "\n\n" + get_msg(lang, "budget_warn_exceeded", spent=f"{int(t_spent):,}", budget=f"{int(budget):,}")
            elif t_spent > budget * 0.9:
                msg += "\n\n" + get_msg(lang, "budget_warn_close", spent=f"{int(t_spent):,}", budget=f"{int(budget):,}")
    
    if streak > 1:
        msg += "\n" + get_msg(lang, "strike", strike=streak)
    
    await callback.message.edit_text(msg)
    await state.clear()
    await callback.answer()

@router.message(F.voice)
async def process_voice(message: types.Message, state: FSMContext, bot: Bot):
    lang = await db_manager.get_user_language(message.from_user.id)
    wait_msg = await message.answer(get_msg(lang, "thinking"))
    
    file_id = message.voice.file_id
    file = await bot.get_file(file_id)
    file_path = file.file_path
    
    # Create temp directory if it doesn't exist
    os.makedirs("temp", exist_ok=True)
    local_file_path = f"temp/{file_id}.ogg"
    
    await bot.download_file(file_path, local_file_path)
    
    try:
        parsed = await parse_audio_file(local_file_path)
        
        amount = parsed.get("amount")
        category = parsed.get("category")
        parsed_type = parsed.get("type", "expense")
        currency = parsed.get("currency", "AMD")
        
        if not amount:
            await wait_msg.edit_text(get_msg(lang, "not_understood"))
            return

        if currency != "AMD":
            from logic.currency import convert_to_amd
            amount = await convert_to_amd(amount, currency)
            
        dicts = INCOME_CATEGORIES if parsed_type == "income" else CATEGORIES
            
        if category and category in dicts.values():
            if parsed_type == "income":
                streak = await db_manager.add_income(message.from_user.id, amount, category)
                ui_category = get_category_name(category, lang, is_income=True)
                msg = get_msg(lang, "saved_income", amount=f"{int(amount):,}", category=ui_category)
            else:
                streak = await db_manager.add_expense(message.from_user.id, amount, category)
                ui_category = get_category_name(category, lang, is_income=False)
                msg = get_msg(lang, "saved_expense", amount=f"{int(amount):,}", category=ui_category)
                
            if streak > 1:
                msg += "\n" + get_msg(lang, "strike", strike=streak)
            await wait_msg.edit_text(msg)
            await state.clear()
        else:
            await state.update_data(amount=amount)
            builder = InlineKeyboardBuilder()
            type_lbl = "income" if parsed_type == "income" else "expense"
            for key, name in dicts.items():
                btn_text = get_category_name(key, lang, is_income=(type_lbl=="income"))
                builder.button(text=btn_text, callback_data=f"cat_{type_lbl}_{key}")
            builder.adjust(2)
            await wait_msg.edit_text(f"{int(amount):,} AMD. " + get_msg(lang, "choose_cat"), reply_markup=builder.as_markup())
            
    finally:
        if os.path.exists(local_file_path):
            os.remove(local_file_path)
        try:
            await message.delete()
        except Exception:
            pass

@router.message(ExpenseState.waiting_for_amount)
@router.message(ExpenseState.waiting_for_income)
@router.message(F.text & ~F.text.startswith("/"))
async def process_text_or_amount(message: types.Message, state: FSMContext):
    lang = await db_manager.get_user_language(message.from_user.id)
    
    ignore_texts = [
        get_msg(l, btn) for l in ["ru", "en", "hy"] 
        for btn in ["btn_expense", "btn_income", "btn_stats", "btn_history", "btn_lang", "btn_rates"]
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
        type_lbl = "income" if forced_type == "income" else "expense"
        
        for key, name in dicts.items():
            btn_text = get_category_name(key, lang, is_income=(type_lbl=="income"))
            builder.button(text=btn_text, callback_data=f"cat_{type_lbl}_{key}")
        builder.adjust(2)
        
        await wait_msg.edit_text(get_msg(lang, "choose_cat"), reply_markup=builder.as_markup())
        return

    parsed = await parse_expense_text(message.text)
    
    amount = parsed.get("amount")
    category = parsed.get("category")
    parsed_type = parsed.get("type", "expense")
    currency = parsed.get("currency", "AMD")
    
    if forced_type:
        parsed_type = forced_type
    
    if not amount:
        await wait_msg.edit_text(get_msg(lang, "not_understood"))
        await state.clear()
        return
        
    if currency != "AMD":
        amount = await convert_to_amd(amount, currency)
        
    dicts = INCOME_CATEGORIES if parsed_type == "income" else CATEGORIES
        
    if category and category in dicts.values():
        if parsed_type == "income":
            streak = await db_manager.add_income(message.from_user.id, amount, category)
            ui_category = get_category_name(category, lang, is_income=True)
            msg = get_msg(lang, "saved_income", amount=f"{int(amount):,}", category=ui_category)
        else:
            streak = await db_manager.add_expense(message.from_user.id, amount, category)
            ui_category = get_category_name(category, lang, is_income=False)
            msg = get_msg(lang, "saved_expense", amount=f"{int(amount):,}", category=ui_category)
            
        if streak > 1:
            msg += "\n" + get_msg(lang, "strike", strike=streak)
        await wait_msg.edit_text(msg)
        await state.clear()
    else:
        await state.update_data(amount=amount)
        builder = InlineKeyboardBuilder()
        type_lbl = "income" if parsed_type == "income" else "expense"
        for key, name in dicts.items():
            btn_text = get_category_name(key, lang, is_income=(type_lbl=="income"))
            builder.button(text=btn_text, callback_data=f"cat_{type_lbl}_{key}")
        builder.adjust(2)
        await wait_msg.edit_text(f"{amount} AMD. " + get_msg(lang, "choose_cat"), reply_markup=builder.as_markup())
