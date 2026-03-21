from config import NORMS
from datetime import datetime
import calendar

def get_days_in_month(year, month):
    return calendar.monthrange(year, month)[1]

def analyze_expenses(total_spent, category_sums, lang="ru"):
    from utils.locales import get_category_name, get_msg
    report = []
    advice = []
    potential_savings = 0
    
    for category, amount in category_sums:
        percentage = (amount / total_spent) * 100 if total_spent > 0 else 0
        norm_range = NORMS.get(category)
        translated_cat = get_category_name(category, lang)
        
        status_emoji = "✅"
        if norm_range:
            min_norm, max_norm = norm_range
            max_norm_pct = max_norm * 100
            
            if percentage > max_norm_pct:
                status_emoji = "⚠️"
                diff_pct = percentage - max_norm_pct
                excess_amount = (diff_pct / 100) * total_spent
                potential_savings += excess_amount
                advice.append(get_msg(lang, "advice_text", category=translated_cat, amount=f"{int(excess_amount):,}"))
            elif percentage > (max_norm_pct * 0.9):
                status_emoji = "🟡"
        
        report.append(f"{status_emoji} {translated_cat}: {int(amount):,} AMD ({percentage:.1f}%)")

    # Forecast
    today = datetime.now()
    days_passed = today.day
    days_in_month = get_days_in_month(today.year, today.month)
    
    avg_per_day = total_spent / days_passed if days_passed > 0 else 0
    forecast = avg_per_day * days_in_month
    
    # Yearly savings psychological trigger
    yearly_savings = potential_savings * 12
    
    summary = {
        "report_lines": report,
        "advice": advice,
        "forecast": int(forecast),
        "potential_yearly_savings": int(yearly_savings)
    }
    
    return summary
