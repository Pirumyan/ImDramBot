import aiohttp
import logging

async def get_all_rates() -> dict:
    rates = {"USD": 405.0, "EUR": 435.0, "RUB": 4.5}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://open.er-api.com/v6/latest/AMD") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    rates_api = data.get("rates", {})
                    if "USD" in rates_api:
                        rates["USD"] = round(1 / rates_api["USD"], 2)
                    if "EUR" in rates_api:
                        rates["EUR"] = round(1 / rates_api["EUR"], 2)
                    if "RUB" in rates_api:
                        rates["RUB"] = round(1 / rates_api["RUB"], 2)
    except Exception as e:
        logging.error(f"Error fetching ALL currency from API: {e}")
    return rates

async def convert_to_amd(amount: float, currency: str) -> float:
    if not currency:
        return amount
        
    currency = currency.upper().strip()
    if currency in ["AMD", "DRAM", "ДРАМ", "ԴՐԱՄ"]:
        return amount
        
    rates = await get_all_rates()
        
    if currency in rates:
        return round(amount * rates[currency], 2)
        
    return amount
