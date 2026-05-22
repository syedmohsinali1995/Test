import httpx
from config import settings

VAPI_BASE_URL = "https://api.vapi.ai"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.vapi_api_key}",
        "Content-Type": "application/json",
    }


# ── Assistants ────────────────────────────────────────────────────────────────

async def create_assistant(config: dict) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{VAPI_BASE_URL}/assistant",
            json=config,
            headers=_headers(),
            timeout=30,
        )
        r.raise_for_status()
        return r.json()


async def get_assistant(assistant_id: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{VAPI_BASE_URL}/assistant/{assistant_id}",
            headers=_headers(),
            timeout=15,
        )
        r.raise_for_status()
        return r.json()


async def update_assistant(assistant_id: str, config: dict) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.patch(
            f"{VAPI_BASE_URL}/assistant/{assistant_id}",
            json=config,
            headers=_headers(),
            timeout=30,
        )
        r.raise_for_status()
        return r.json()


# ── Calls ─────────────────────────────────────────────────────────────────────

async def make_call(phone_number: str, assistant_id: str, metadata: dict = None) -> dict:
    """Initiate an outbound call via Vapi."""
    payload = {
        "assistantId": assistant_id,
        "customer": {"number": phone_number},
        "phoneNumberId": settings.vapi_phone_number_id,
    }
    if metadata:
        payload["metadata"] = metadata

    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{VAPI_BASE_URL}/call/phone",
            json=payload,
            headers=_headers(),
            timeout=30,
        )
        r.raise_for_status()
        return r.json()


async def get_call(call_id: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{VAPI_BASE_URL}/call/{call_id}",
            headers=_headers(),
            timeout=15,
        )
        r.raise_for_status()
        return r.json()


async def list_calls(limit: int = 20) -> list:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{VAPI_BASE_URL}/call",
            params={"limit": limit},
            headers=_headers(),
            timeout=15,
        )
        r.raise_for_status()
        return r.json()


# ── Phone Numbers ─────────────────────────────────────────────────────────────

async def list_phone_numbers() -> list:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{VAPI_BASE_URL}/phone-number",
            headers=_headers(),
            timeout=15,
        )
        r.raise_for_status()
        return r.json()
