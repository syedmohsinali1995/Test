"""
Property listings knowledge base.
Loads properties from data/properties.json and provides a search function
that the AI agent calls as a tool during live calls.
"""

import json
import os
from typing import List, Dict, Any

# Absolute path — works locally, in Docker (/app), and on Railway
_BASE_DIR        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROPERTIES_FILE = os.path.join(_BASE_DIR, "data", "properties.json")


def _load_properties() -> List[dict]:
    if not os.path.exists(_PROPERTIES_FILE):
        print(f"[KB] Warning: {_PROPERTIES_FILE} not found — returning empty list")
        return []
    with open(_PROPERTIES_FILE, encoding="utf-8") as f:
        return json.load(f)


_PROPERTIES = _load_properties()


def search_properties(
    city: str = "",
    area: str = "",
    intent: str = "",          # buy / rent
    property_type: str = "",   # house / apartment / plot / office / commercial
    bedrooms: int = 0,
    max_budget: int = 0,
    min_budget: int = 0,
) -> Dict[str, Any]:
    """
    Search property listings based on filters.
    Returns up to 3 matching properties formatted for the AI to read aloud in Urdu.
    """
    results = []

    for prop in _PROPERTIES:
        if not prop.get("available"):
            continue

        # City filter
        if city and city.lower() not in prop.get("city", "").lower():
            continue

        # Area filter
        if area and area.lower() not in prop.get("area", "").lower():
            continue

        # Intent filter (buy/rent)
        if intent and intent not in prop.get("intent", []):
            continue

        # Property type filter
        if property_type and property_type != "any":
            if prop.get("type") != property_type:
                continue

        # Bedrooms filter (skip for plots/offices)
        if bedrooms and prop.get("bedrooms", 0) > 0:
            if prop["bedrooms"] < bedrooms:
                continue

        # Budget filter
        price = prop["price_rent_monthly"] if intent == "rent" else prop["price_buy"]
        if price == 0:
            pass
        else:
            if max_budget and price > max_budget:
                continue
            if min_budget and price < min_budget:
                continue

        results.append(prop)

    if not results:
        return {
            "found": False,
            "message": "معاف کریں، آپ کی ضروریات کے مطابق ابھی کوئی جائیداد دستیاب نہیں ہے۔ کیا میں آپ کی ضروریات نوٹ کر لوں تاکہ ہم جائیداد ملنے پر آپ سے رابطہ کریں؟",
            "properties": [],
        }

    # Format top 3 for voice readout
    top = results[:3]
    formatted = []
    for p in top:
        price_str = _format_price(p, intent)
        formatted.append({
            "id": p["id"],
            "title": p["title"],
            "area": p["area"],
            "bedrooms": p["bedrooms"],
            "size_marla": p["size_marla"],
            "price": price_str,
            "features": ", ".join(p.get("features", [])[:3]),
            "agent_phone": p["agent_phone"],
        })

    summary = _build_voice_summary(formatted, intent)

    return {
        "found": True,
        "count": len(results),
        "message": summary,
        "properties": formatted,
    }


def _format_price(prop: dict, intent: str) -> str:
    if intent == "rent":
        price = prop.get("price_rent_monthly", 0)
        if price:
            return f"{price:,} روپے ماہانہ"
        return "قیمت دستیاب نہیں"
    else:
        price = prop.get("price_buy", 0)
        if price >= 10_000_000:
            crore = price / 10_000_000
            return f"{crore:.1f} کروڑ روپے"
        elif price >= 100_000:
            lakh = price / 100_000
            return f"{lakh:.0f} لاکھ روپے"
        return f"{price:,} روپے"


def _build_voice_summary(properties: List[dict], intent: str) -> str:
    if len(properties) == 1:
        p = properties[0]
        return (
            f"ہمارے پاس ایک جائیداد دستیاب ہے: {p['title']}، {p['area']} میں، "
            f"قیمت {p['price']}۔ کیا آپ اسے دیکھنا چاہیں گے؟"
        )
    lines = [f"ہمارے پاس {len(properties)} جائیدادیں دستیاب ہیں:"]
    for i, p in enumerate(properties, 1):
        lines.append(f"نمبر {i}: {p['title']}، {p['area']}، قیمت {p['price']}۔")
    lines.append("کون سی جائیداد آپ کو پسند آئی؟ میں ملاقات بک کر سکتی ہوں۔")
    return " ".join(lines)
