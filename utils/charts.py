import matplotlib.pyplot as plt
import io
from config import NORMS
from utils.locales import get_category_name

def generate_pie_chart(category_sums, total_spent, lang):
    labels = [get_category_name(c, lang) for c, _ in category_sums]
    original_labels = [c for c, _ in category_sums]
    amounts = [a for _, a in category_sums]
    
    # Sort by amount for better visual
    data = sorted(zip(labels, amounts, original_labels), key=lambda x: x[1], reverse=True)
    labels = [d[0] for d in data]
    amounts = [d[1] for d in data]
    original_labels = [d[2] for d in data]
    
    colors = []
    for label, amount, orig_label in zip(labels, amounts, original_labels):
        pct = (amount / total_spent) if total_spent > 0 else 0
        norm = NORMS.get(orig_label)
        if norm:
            _, max_norm = norm
            if pct > max_norm:
                colors.append('#ff4d4d') # Red
            elif pct > max_norm * 0.9:
                colors.append('#ffcc00') # Yellow
            else:
                colors.append('#2eb82e') # Green
        else:
            colors.append('#bdc3c7') # Gray for "Other"
            
    fig, ax = plt.subplots(figsize=(8, 8))
    wedges, texts, autotexts = ax.pie(
        amounts, 
        labels=labels, 
        autopct='%1.1f%%', 
        startangle=140, 
        colors=colors,
        pctdistance=0.85
    )
    
    plt.setp(autotexts, size=10, weight="bold", color="white")
    plt.setp(texts, size=12)
    
    # Draw circle for donut chart effect
    centre_circle = plt.Circle((0,0), 0.70, fc='white')
    fig.gca().add_artist(centre_circle)
    
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    buf.seek(0)
    plt.close()
    return buf
