"""
WhatsApp follow-up service using Twilio WhatsApp API.
Sends automatic messages after call events:
  - Viewing confirmation after booking
  - Lead acknowledgment after qualification
  - Missed call notification
"""

from twilio.rest import Client
from config import settings

_client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

# Twilio WhatsApp sandbox number (for testing)
# For production, replace with your approved WhatsApp Business number
WHATSAPP_FROM = f"whatsapp:{settings.twilio_whatsapp_number}"


def _send(to_number: str, body: str) -> bool:
    """Send a WhatsApp message. Returns True on success."""
    if not to_number or not settings.twilio_account_sid:
        print("[WhatsApp] Skipped — Twilio not configured")
        return False

    # Ensure number is in E.164 format
    if not to_number.startswith("+"):
        to_number = "+" + to_number

    try:
        message = _client.messages.create(
            from_=WHATSAPP_FROM,
            to=f"whatsapp:{to_number}",
            body=body,
        )
        print(f"[WhatsApp] Sent to {to_number} — SID: {message.sid}")
        return True
    except Exception as exc:
        print(f"[WhatsApp] Error sending to {to_number}: {exc}")
        return False


# ── Message templates ─────────────────────────────────────────────────────────

def send_viewing_confirmation(
    phone_number: str,
    customer_name: str,
    property_address: str,
    viewing_date: str,
    viewing_time: str,
    viewing_id: str,
    business_name: str = "",
) -> bool:
    body = (
        f"السلام علیکم {customer_name} صاحب/صاحبہ! 🏠\n\n"
        f"آپ کی جائیداد دیکھنے کی ملاقات کنفرم ہو گئی ہے۔\n\n"
        f"📋 بکنگ نمبر: {viewing_id}\n"
        f"🏡 جائیداد: {property_address}\n"
        f"📅 تاریخ: {viewing_date}\n"
        f"⏰ وقت: {viewing_time}\n\n"
        f"ہمارا ایجنٹ مقررہ وقت پر آپ سے ملے گا۔\n"
        f"کسی بھی سوال کے لیے یہاں جواب دیں۔\n\n"
        f"شکریہ! — {business_name or 'رئیل اسٹیٹ ٹیم'}"
    )
    return _send(phone_number, body)


def send_lead_acknowledgment(
    phone_number: str,
    customer_name: str,
    intent: str,
    area: str,
    lead_id: str,
    business_name: str = "",
) -> bool:
    intent_urdu = "خریدنے" if intent == "buy" else "کرایہ لینے"
    body = (
        f"السلام علیکم {customer_name} صاحب/صاحبہ! 👋\n\n"
        f"آپ کی {area} میں جائیداد {intent_urdu} کی دلچسپی نوٹ کر لی گئی ہے۔\n\n"
        f"📋 لیڈ نمبر: {lead_id}\n\n"
        f"ہمارا سینیئر ایجنٹ جلد آپ سے رابطہ کرے گا اور آپ کی ضروریات کے مطابق "
        f"بہترین جائیداد تلاش کرنے میں مدد کرے گا۔\n\n"
        f"شکریہ! — {business_name or 'رئیل اسٹیٹ ٹیم'}"
    )
    return _send(phone_number, body)


def send_missed_call_notification(
    phone_number: str,
    business_name: str = "",
    retry_number: int = 1,
) -> bool:
    body = (
        f"السلام علیکم! 📞\n\n"
        f"ہم نے آپ سے {business_name or 'ہماری رئیل اسٹیٹ کمپنی'} کی طرف سے "
        f"رابطہ کرنے کی کوشش کی لیکن آپ دستیاب نہیں تھے۔\n\n"
        f"ہم جلد دوبارہ کال کریں گے۔ اگر آپ ابھی بات کرنا چاہتے ہیں تو "
        f"اس نمبر پر کال کریں یا یہاں پیغام بھیجیں۔\n\n"
        f"شکریہ!"
    )
    return _send(phone_number, body)


def send_inquiry_followup(
    phone_number: str,
    customer_name: str,
    inquiry_id: str,
    business_name: str = "",
) -> bool:
    body = (
        f"السلام علیکم {customer_name} صاحب/صاحبہ! 🏠\n\n"
        f"آپ کی انکوائری ({inquiry_id}) موصول ہو گئی ہے۔\n\n"
        f"ہماری ٹیم آپ کے سوال کا جواب تیار کر رہی ہے اور "
        f"جلد آپ سے رابطہ کرے گی۔\n\n"
        f"شکریہ! — {business_name or 'رئیل اسٹیٹ ٹیم'}"
    )
    return _send(phone_number, body)
