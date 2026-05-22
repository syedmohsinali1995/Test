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
    business_hours: str = "Monday to Saturday, 9 AM to 6 PM"


@router.post("/save-keys")
async def save_and_setup(
    body: SetupRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    # Step 1: Save API keys first (so they're not lost even if Vapi fails)
    tenant.vapi_api_key           = body.vapi_api_key
    tenant.vapi_phone_number_id   = body.vapi_phone_number_id
    tenant.anthropic_api_key      = body.anthropic_api_key
    tenant.twilio_account_sid     = body.twilio_account_sid
    tenant.twilio_auth_token      = body.twilio_auth_token
    tenant.twilio_whatsapp_number = body.twilio_whatsapp_number
    tenant.business_hours         = body.business_hours
    db.commit()

    # Step 2: Create Vapi assistant
    try:
        assistant_id = await _create_vapi_assistant(tenant)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Setup Error] {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Setup error: {type(e).__name__}: {str(e)}"
        )

    # Step 3: Save assistant ID and mark complete
    tenant.vapi_assistant_id = assistant_id
    tenant.is_setup_complete  = True
    db.commit()

    return {
        "message": "Setup complete! Your AI calling agent is ready.",
        "assistant_id": assistant_id,
    }


@router.get("/status")
def setup_status(tenant: Tenant = Depends(get_current_tenant)):
    return {
        "is_setup_complete":  tenant.is_setup_complete,
        "has_vapi_key":       bool(tenant.vapi_api_key),
        "has_assistant":      bool(tenant.vapi_assistant_id),
        "has_phone_number":   bool(tenant.vapi_phone_number_id),
        "has_anthropic":      bool(tenant.anthropic_api_key),
        "has_twilio":         bool(tenant.twilio_account_sid),
    }


async def _create_vapi_assistant(tenant: Tenant) -> str:
    """Create Urdu real estate AI assistant on Vapi and return its ID."""

    webhook_base = settings.public_url.rstrip("/")
    tool_url     = f"{webhook_base}/webhook/tool/{tenant.id}"
    vapi_url     = f"{webhook_base}/webhook/vapi/{tenant.id}"

    system_prompt = f"""You are a professional Urdu real estate assistant named "Zainab" (زینب).
You work for {tenant.business_name}. Business hours: {tenant.business_hours}.

IMPORTANT: Always speak in URDU language only, regardless of what language the customer uses.

Your tasks:
1. Search properties using search_properties tool when customer asks
2. Book property viewings using book_viewing tool
3. Save qualified leads using save_lead tool
4. Log general inquiries using log_inquiry tool
5. Transfer to human agent using transfer_to_agent when needed

Lead qualification questions (ask in Urdu):
- Do you want to buy or rent?
- What is your budget?
- Which area do you prefer?
- How many bedrooms do you need?
- When do you need it?

Keep responses SHORT (2-3 sentences max) as this is a phone call.
Always respond in Urdu script."""

    config = {
        "name": f"{tenant.business_name} - Urdu AI Agent",
        "firstMessage": f"السلام علیکم! {tenant.business_name} میں خوش آمدید۔ میں زینب ہوں، آپ کی کیا مدد کر سکتی ہوں؟",
        "model": {
            "provider": "anthropic",
            "model": "claude-3-5-sonnet-20241022",
            "systemPrompt": system_prompt,
            "temperature": 0.7,
            "maxTokens": 250,
            "tools": _build_tools(tool_url),
        },
        "voice": {
            "provider": "openai",
            "voiceId": "nova",
        },
        "transcriber": {
            "provider": "deepgram",
            "model": "nova-2",
            "language": "ur",
        },
        "endCallMessage": "خدا حافظ! آپ کا دن اچھا گزرے۔",
        "endCallPhrases": ["خدا حافظ", "الوداع", "بائے", "bye", "goodbye", "ok bye"],
        "silenceTimeoutSeconds": 30,
        "maxDurationSeconds": 1800,
        "recordingEnabled": True,
        "backchannelingEnabled": False,
        "serverUrl": vapi_url,
    }

    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://api.vapi.ai/assistant",
            json=config,
            headers={
                "Authorization": f"Bearer {tenant.vapi_api_key}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )

        if not r.is_success:
            error_body = r.text
            print(f"[Vapi Error] {r.status_code}: {error_body}")
            raise HTTPException(
                status_code=400,
                detail=f"Vapi API error ({r.status_code}): {error_body}"
            )

        data = r.json()
        assistant_id = data.get("id")
        if not assistant_id:
            raise HTTPException(status_code=500, detail=f"Vapi returned no assistant ID: {data}")

        print(f"[Setup] Assistant created: {assistant_id} for {tenant.business_name}")
        return assistant_id


def _build_tools(tool_url: str) -> list:
    return [
        {
            "type": "function",
            "function": {
                "name": "search_properties",
                "description": "Search property listings when customer asks about properties",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city":          {"type": "string"},
                        "area":          {"type": "string"},
                        "intent":        {"type": "string", "enum": ["buy", "rent"]},
                        "property_type": {"type": "string", "enum": ["house", "apartment", "plot", "office", "any"]},
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
                "description": "Book a property viewing appointment",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_name":    {"type": "string"},
                        "phone_number":     {"type": "string"},
                        "property_address": {"type": "string"},
                        "viewing_date":     {"type": "string"},
                        "viewing_time":     {"type": "string"},
                        "property_type":    {"type": "string"},
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
                "description": "Save a qualified lead after collecting their requirements",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_name":  {"type": "string"},
                        "phone_number":   {"type": "string"},
                        "intent":         {"type": "string", "enum": ["buy", "rent", "sell", "invest"]},
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
                "description": "Log a general property inquiry",
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
                "description": "Transfer call to a human real estate agent",
                "parameters": {
                    "type": "object",
                    "properties": {"reason": {"type": "string"}},
                    "required": ["reason"],
                },
            },
            "server": {"url": tool_url},
        },
    ]
