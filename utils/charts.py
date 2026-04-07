import urllib.parse
import json
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
            
    chart_config = {
        "type": "outlabeledPie",
        "data": {
            "labels": labels,
            "datasets": [{"backgroundColor": colors, "data": amounts}]
        },
        "options": {
            "plugins": {
                "legend": False,
                "outlabels": {
                    "text": "%l %p",
                    "color": "white",
                    "stretch": 35,
                    "font": {
                        "resizable": True,
                        "minSize": 12,
                        "maxSize": 18
                    }
                }
            }
        }
    }
    
    encoded_config = urllib.parse.quote(json.dumps(chart_config))
    return f"https://quickchart.io/chart?c={encoded_config}&w=600&h=600&bkg=transparent"
