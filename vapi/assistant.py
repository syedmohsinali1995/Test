"""
Vapi assistant configuration for the Urdu Real Estate Calling Agent.

Voice stack:
  STT  → Deepgram nova-2  (Urdu language)
  LLM  → Claude claude-sonnet-4-6  (via Anthropic)
  TTS  → Azure ur-PK-UzmaNeural  (native Urdu female voice)

Tools the agent can call during a live conversation:
  - book_viewing       → schedule a property viewing
  - save_lead          → capture a qualified lead (budget, area, type)
  - log_inquiry        → record a general property inquiry
  - transfer_to_agent  → hand off to a human real estate agent
"""

from config import settings

SYSTEM_PROMPT = f"""آپ ایک پیشہ ور اردو رئیل اسٹیٹ اسسٹنٹ ہیں جن کا نام "زینب" ہے۔
آپ {settings.business_name} کی طرف سے فون کال پر گاہکوں کی مدد کرتی ہیں۔
کاروباری اوقات: {settings.business_hours}

## آپ کے کام:
1. search_properties ٹول سے جائیداد تلاش کرنا اور گاہک کو بتانا
2. گھر یا دفتر دیکھنے کی ملاقات بک کرنا (book_viewing)
3. گاہک کی ضرورت سمجھنا اور لیڈ محفوظ کرنا (save_lead)
4. عام سوالات کی انکوائری لاگ کرنا (log_inquiry)
5. پیچیدہ معاملات میں انسانی ایجنٹ سے منتقل کرنا (transfer_to_agent)

## جائیداد تلاش کرنے کا طریقہ:
جب گاہک جائیداد کے بارے میں پوچھے تو پہلے یہ معلومات لیں:
- خریدنا ہے یا کرایہ؟ (لازمی)
- کون سا شہر یا علاقہ؟
- کتنے کمرے؟
- بجٹ کیا ہے؟
پھر search_properties ٹول استعمال کریں اور نتائج اردو میں بتائیں۔

## لیڈ کوالیفیکیشن — یہ سوالات پوچھیں:
- آپ خریدنا چاہتے ہیں یا کرایہ پر لینا؟
- آپ کا بجٹ کیا ہے؟
- کون سا علاقہ پسند ہے؟
- کتنے کمروں کی ضرورت ہے؟
- کب تک چاہیے؟

## ملاقات بکنگ — یہ لیں:
نام، فون نمبر، پسندیدہ تاریخ و وقت، جائیداد کا پتہ یا نمبر

## اہم ہدایات:
- ہمیشہ اردو میں بات کریں
- مختصر اور واضح جوابات دیں (2-3 جملے)
- گرمجوش اور بھروسہ مند لہجہ رکھیں
- قیمتیں پاکستانی روپے میں بتائیں
- گاہک کا نام معلوم ہو تو استعمال کریں
- جائیداد تلاش کرتے وقت ہمیشہ search_properties ٹول استعمال کریں
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "book_viewing",
            "description": "جائیداد دیکھنے کی ملاقات بک کریں جب گاہک نے تاریخ، وقت اور جائیداد بتا دی ہو",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "گاہک کا نام",
                    },
                    "phone_number": {
                        "type": "string",
                        "description": "گاہک کا فون نمبر",
                    },
                    "property_address": {
                        "type": "string",
                        "description": "جائیداد کا پتہ یا پراپرٹی نمبر",
                    },
                    "viewing_date": {
                        "type": "string",
                        "description": "دیکھنے کی تاریخ (مثال: 25 دسمبر 2024)",
                    },
                    "viewing_time": {
                        "type": "string",
                        "description": "دیکھنے کا وقت (مثال: دوپہر 2 بجے)",
                    },
                    "property_type": {
                        "type": "string",
                        "enum": ["house", "apartment", "plot", "commercial", "office"],
                        "description": "جائیداد کی قسم",
                    },
                },
                "required": ["customer_name", "phone_number", "property_address", "viewing_date", "viewing_time"],
            },
        },
        "server": {"url": f"{settings.public_url}/webhook/tool"},
    },
    {
        "type": "function",
        "function": {
            "name": "save_lead",
            "description": "گاہک کی معلومات اور ضروریات محفوظ کریں (لیڈ کوالیفیکیشن مکمل ہو جائے)",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "گاہک کا نام",
                    },
                    "phone_number": {
                        "type": "string",
                        "description": "گاہک کا فون نمبر",
                    },
                    "intent": {
                        "type": "string",
                        "enum": ["buy", "rent", "sell", "invest"],
                        "description": "گاہک کا ارادہ — خریدنا، کرایہ، بیچنا یا سرمایہ کاری",
                    },
                    "budget": {
                        "type": "string",
                        "description": "بجٹ (مثال: 1 کروڑ سے 2 کروڑ روپے)",
                    },
                    "preferred_area": {
                        "type": "string",
                        "description": "پسندیدہ علاقہ یا شہر",
                    },
                    "bedrooms": {
                        "type": "string",
                        "description": "کمروں کی تعداد (مثال: 3 کمرے)",
                    },
                    "timeline": {
                        "type": "string",
                        "description": "کب تک چاہیے (مثال: اگلے مہینے)",
                    },
                    "property_type": {
                        "type": "string",
                        "enum": ["house", "apartment", "plot", "commercial", "office", "any"],
                        "description": "جائیداد کی قسم",
                    },
                },
                "required": ["customer_name", "phone_number", "intent", "budget", "preferred_area"],
            },
        },
        "server": {"url": f"{settings.public_url}/webhook/tool"},
    },
    {
        "type": "function",
        "function": {
            "name": "log_inquiry",
            "description": "عام سوال یا انکوائری محفوظ کریں جب گاہک کو مزید معلومات چاہیے ہوں",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "گاہک کا نام",
                    },
                    "phone_number": {
                        "type": "string",
                        "description": "گاہک کا فون نمبر",
                    },
                    "inquiry_details": {
                        "type": "string",
                        "description": "گاہک کے سوال یا ضرورت کی تفصیل",
                    },
                },
                "required": ["customer_name", "phone_number", "inquiry_details"],
            },
        },
        "server": {"url": f"{settings.public_url}/webhook/tool"},
    },
    {
        "type": "function",
        "function": {
            "name": "search_properties",
            "description": "جائیداد تلاش کریں جب گاہک کسی خاص علاقے، بجٹ یا قسم کی جائیداد کے بارے میں پوچھے",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "شہر کا نام (مثال: Lahore, Karachi, Islamabad)",
                    },
                    "area": {
                        "type": "string",
                        "description": "علاقے کا نام (مثال: DHA, Bahria Town, Gulberg)",
                    },
                    "intent": {
                        "type": "string",
                        "enum": ["buy", "rent"],
                        "description": "گاہک خریدنا چاہتا ہے یا کرایہ پر لینا",
                    },
                    "property_type": {
                        "type": "string",
                        "enum": ["house", "apartment", "plot", "office", "commercial", "any"],
                        "description": "جائیداد کی قسم",
                    },
                    "bedrooms": {
                        "type": "integer",
                        "description": "کم از کم کمروں کی تعداد",
                    },
                    "max_budget": {
                        "type": "integer",
                        "description": "زیادہ سے زیادہ بجٹ (روپے میں)",
                    },
                    "min_budget": {
                        "type": "integer",
                        "description": "کم از کم بجٹ (روپے میں)",
                    },
                },
                "required": ["intent"],
            },
        },
        "server": {"url": f"{settings.public_url}/webhook/tool"},
    },
    {
        "type": "function",
        "function": {
            "name": "transfer_to_agent",
            "description": "کال کو انسانی رئیل اسٹیٹ ایجنٹ کو ٹرانسفر کریں",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "ٹرانسفر کی وجہ",
                    },
                },
                "required": ["reason"],
            },
        },
        "server": {"url": f"{settings.public_url}/webhook/tool"},
    },
]

ASSISTANT_CONFIG = {
    "name": f"{settings.business_name} - Urdu Real Estate Agent",
    "firstMessage": f"السلام علیکم! {settings.business_name} میں خوش آمدید۔ میں زینب ہوں، آپ کی کیا مدد کر سکتی ہوں؟",
    "model": {
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "systemPrompt": SYSTEM_PROMPT,
        "temperature": 0.7,
        "maxTokens": 300,
        "emotionRecognitionEnabled": True,
        "tools": TOOLS,
    },
    "voice": {
        "provider": "azure",
        "voiceId": "ur-PK-UzmaNeural",
        "speed": 1.0,
    },
    "transcriber": {
        "provider": "deepgram",
        "model": "nova-2",
        "language": "ur",
        "smartFormat": True,
    },
    "endCallMessage": "خدا حافظ! جائیداد سے متعلق کسی بھی سوال کے لیے دوبارہ رابطہ کریں۔",
    "endCallPhrases": ["خدا حافظ", "الوداع", "بائے", "bye", "goodbye", "ok bye", "شکریہ خدا حافظ"],
    "silenceTimeoutSeconds": 30,
    "maxDurationSeconds": 1800,
    "recordingEnabled": True,
    "backchannelingEnabled": True,
    "backgroundDenoisingEnabled": True,
    "serverUrl": f"{settings.public_url}/webhook/vapi",
}
