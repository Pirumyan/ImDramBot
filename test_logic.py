from logic.analyzer import analyze_expenses

def test_analysis():
    print("🧪 Тестирование логики анализа...")
    
    total_spent = 200000
    category_sums = [
        ("Еда 🍔", 80000),      # 40% (Норма до 35%)
        ("Жильё 🏠", 60000),    # 30% (Норма 25-35%)
        ("Транспорт 🚕", 20000), # 10% (Норма 10-20%)
        ("Кафе и доставка ☕", 40000) # 20% (Норма до 15%)
    ]
    
    analysis = analyze_expenses(total_spent, category_sums)
    
    print(f"\nОбщий расход: {total_spent} AMD")
    print("Отчет:")
    for line in analysis["report_lines"]:
        print(line)
        
    print("\nСоветы:")
    for advice in analysis["advice"]:
        print(advice)
        
    print(f"\nПрогноз на месяц: {analysis['forecast']} AMD")
    print(f"Потенциальная экономия за год: {analysis['potential_yearly_savings']} AMD")

if __name__ == "__main__":
    test_analysis()
