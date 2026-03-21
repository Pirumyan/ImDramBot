import os
import json
import logging
from config import GEMINI_API_KEY, CATEGORIES, INCOME_CATEGORIES
import google.generativeai as genai

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

generation_config = {
    "temperature": 0.0,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 150,
}

SYSTEM_PROMPT = f"""
Ты интеллектуальный помощник учета финансов. Твоя задача — извлекать тип (доход/расход), сумму, валюту и категорию из сообщения пользователя о финансах.

Возможные категории РАСХОДОВ: {', '.join(CATEGORIES.values())}
Возможные источники ДОХОДОВ: {', '.join(INCOME_CATEGORIES.values())}

Алгоритм:
1. Пойми это трата (expense) или доход (income, например "зарплата", "пополнил", "пришло", "доход").
2. Найди сумму. Если есть 'k' (например 5k) - это 5000.
3. Достань валюту: AMD (драм), USD (доллар), EUR (евро), RUB (рубль). По умолчанию ставь "AMD".
4. Подбери подходящую категорию. Если неясно, ставь null для категории.

Формат ответа СТРОГО JSON:
{{
  "type": "expense" или "income",
  "amount": число_или_null,
  "currency": "AMD",
  "category": "строка_или_null"
}}
Отвечай ТОЛЬКО валидным JSON, без форматирования Markdown (без ```json).
"""

async def parse_expense_text(text: str) -> dict:
    if not GEMINI_API_KEY:
        return {"type": "expense", "amount": None, "currency": "AMD", "category": None}
        
    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash", 
            generation_config=generation_config,
            system_instruction=SYSTEM_PROMPT
        )
        
        response = await model.generate_content_async(text)
        result_text = response.text.strip()
        
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.startswith("```"):
            result_text = result_text[3:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
            
        data = json.loads(result_text.strip())
        
        amount = data.get("amount")
        if amount is not None:
            amount = float(amount)
            
        return {
            "type": data.get("type", "expense"),
            "amount": amount,
            "currency": data.get("currency", "AMD"),
            "category": data.get("category")
        }
    except Exception as e:
        logging.error(f"Error parsing text with Gemini: {e}")
        return {"type": "expense", "amount": None, "currency": "AMD", "category": None}
