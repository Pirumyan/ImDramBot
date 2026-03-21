import aiohttp
import logging

async def convert_to_amd(amount: float, currency: str) -> float:
    if not currency:
        return amount
        
    currency = currency.upper().strip()
    if currency in ["AMD", "DRAM", "ДРАМ", "ԴՐԱՄ"]:
        return amount
        
    rates = {"USD": 405.0, "EUR": 435.0, "RUB": 4.5}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://open.er-api.com/v6/latest/AMD") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    rates_api = data.get("rates", {})
                    if currency in rates_api:
                        rate = rates_api[currency]
                        return round(amount / rate, 2)
    except Exception as e:
        logging.error(f"Error fetching currency from API: {e}")
        
    if currency in rates:
        return round(amount * rates[currency], 2)
        
    return amount
