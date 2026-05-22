"""Setup wizard — saves API keys and creates the Vapi assistant for a tenant."""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from db.database import get_db
from db.models import Tenant
from auth.jwt_utils import get_current_tenant
from config import settings
import httpx

router = APIRouter(prefix="/setup", tags=["Setup"])


class SetupRequest(BaseModel):
    vapi_api_key: str
    vapi_phone_number_id: str
    anthropic_api_key: str
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_number: str = "whatsapp:+14155238886"
    business_hours: str = "پیر سے ہفتہ، صبح 9 بجے سے شام 6 بجے تک"


@router.post("/save-keys")
async def save_and_setup(
    body: SetupRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    Step 1: Save API keys.
    Step 2: Auto-create a Vapi assistant for this tenant.
    Step 3: Mark setup as complete.
    """
    # Save API keys
    tenant.vapi_api_key           = body.vapi_api_key
    tenant.vapi_phone_number_id   = body.vapi_phone_number_id
    tenant.anthropic_api_key      = body.anthropic_api_key
    tenant.twilio_account_sid     = body.twilio_account_sid
    tenant.twilio_auth_token      = body.twilio_auth_token
    tenant.twilio_whatsapp_number = body.twilio_whatsapp_number
    tenant.business_hours         = body.business_hours
    db.commit()

    # Auto-create Vapi assistant
    assistant_id = await _create_vapi_assistant(tenant, db)

    tenant.vapi_assistant_id  = assistant_id
    tenant.is_setup_complete  = True
    db.commit()

    return {
        "message": "Setup complete! Your AI calling agent is ready.",
        "assistant_id": assistant_id,
    }


@router.get("/status")
def setup_status(tenant: Tenant = Depends(get_current_tenant)):
    return {
        "is_setup_complete": tenant.is_setup_complete,
        "has_vapi_key": bool(tenant.vapi_api_key),
        "has_assistant": bool(tenant.vapi_assistant_id),
        "has_phone_number": bool(tenant.vapi_phone_number_id),
        "has_anthropic": bool(tenant.anthropic_api_key),
        "has_twilio": bool(tenant.twilio_account_sid),
    }


async def _create_vapi_assistant(tenant: Tenant, db: Session) -> str:
    from prompts.urdu_system import URDU_SYSTEM_PROMPT

    system_prompt = URDU_SYSTEM_PROMPT.format(
        business_name=tenant.business_name,
        business_hours=tenant.business_hours,
    )

    webhook_base = f"{settings.public_url}/webhook"
    tool_url     = f"{webhook_base}/tool/{tenant.id}"
    vapi_url     = f"{webhook_base}/vapi/{tenant.id}"

    tools = _build_tools(tool_url)

    config = {
        "name": f"{tenant.business_name} - Urdu Real Estate Agent",
        "firstMessage": f"السلام علیکم! {tenant.business_name} میں خوش آمدید۔ میں زینب ہوں، آپ کی کیا مدد کر سکتی ہوں؟",
        "model": {
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "systemPrompt": system_prompt,
            "temperature": 0.7,
            "maxTokens": 300,
            "tools": tools,
        },
        "voice": {"provider": "azure", "voiceId": "ur-PK-UzmaNeural"},
        "transcriber": {"provider": "deepgram", "model": "nova-2", "language": "ur"},
        "endCallMessage": "خدا حافظ! آپ کا دن اچھا گزرے۔",
        "endCallPhrases": ["خدا حافظ", "الوداع", "بائے", "bye", "goodbye"],
        "silenceTimeoutSeconds": 30,
        "maxDurationSeconds": 1800,
        "recordingEnabled": True,
        "backchannelingEnabled": True,
        "backgroundDenoisingEnabled": True,
        "serverUrl": vapi_url,
    }

    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://api.vapi.ai/assistant",
            json=config,
            headers={"Authorization": f"Bearer {tenant.vapi_api_key}"},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["id"]


def _build_tools(tool_url: str) -> list:
    return [
        {
            "type": "function",
            "function": {
                "name": "search_properties",
                "description": "جائیداد تلاش کریں",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city":          {"type": "string"},
                        "area":          {"type": "string"},
                        "intent":        {"type": "string", "enum": ["buy", "rent"]},
                        "property_type": {"type": "string", "enum": ["house","apartment","plot","office","any"]},
                        "bedrooms":      {"type": "integer"},
                        "max_budget":    {"type": "integer"},
                        "min_budget":    {"type": "integer"},
                    },
                    "required": ["intent"],
                },
            },
            "server": {"url": tool_url},
        },
        {
            "type": "function",
            "function": {
                "name": "book_viewing",
                "description": "جائیداد دیکھنے کی ملاقات بک کریں",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_name":     {"type": "string"},
                        "phone_number":      {"type": "string"},
                        "property_address":  {"type": "string"},
                        "viewing_date":      {"type": "string"},
                        "viewing_time":      {"type": "string"},
                        "property_type":     {"type": "string"},
                    },
                    "required": ["customer_name", "phone_number", "property_address", "viewing_date", "viewing_time"],
                },
            },
            "server": {"url": tool_url},
        },
        {
            "type": "function",
            "function": {
                "name": "save_lead",
                "description": "گاہک کی لیڈ محفوظ کریں",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_name":  {"type": "string"},
                        "phone_number":   {"type": "string"},
                        "intent":         {"type": "string", "enum": ["buy","rent","sell","invest"]},
                        "budget":         {"type": "string"},
                        "preferred_area": {"type": "string"},
                        "bedrooms":       {"type": "string"},
                        "timeline":       {"type": "string"},
                        "property_type":  {"type": "string"},
                    },
                    "required": ["customer_name", "phone_number", "intent", "budget", "preferred_area"],
                },
            },
            "server": {"url": tool_url},
        },
        {
            "type": "function",
            "function": {
                "name": "log_inquiry",
                "description": "انکوائری محفوظ کریں",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_name":   {"type": "string"},
                        "phone_number":    {"type": "string"},
                        "inquiry_details": {"type": "string"},
                    },
                    "required": ["customer_name", "phone_number", "inquiry_details"],
                },
            },
            "server": {"url": tool_url},
        },
        {
            "type": "function",
            "function": {
                "name": "transfer_to_agent",
                "description": "انسانی ایجنٹ کو ٹرانسفر کریں",
                "parameters": {
                    "type": "object",
                    "properties": {"reason": {"type": "string"}},
                    "required": ["reason"],
                },
            },
            "server": {"url": tool_url},
        },
    ]
