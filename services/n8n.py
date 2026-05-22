"""
n8n integration service.
When a lead, viewing, inquiry, or missed call event happens,
we fire a webhook to n8n which runs the automation workflow.

n8n then handles:
  - Google Sheets sync
  - CRM (HubSpot / Zoho)
  - Email alerts
  - WhatsApp messages
"""

import httpx
from config import settings


async def trigger(event: str, payload: dict) -> None:
    """
    Fire a webhook to n8n.
    event   : "lead" | "viewing" | "inquiry" | "missed_call" | "call_ended"
    payload : dict of data to send
    """
    if not settings.n8n_webhook_base_url:
        return

    url = f"{settings.n8n_webhook_base_url.rstrip('/')}/{event}"

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json=payload, timeout=10)
            print(f"[n8n] {event} → {r.status_code}")
    except Exception as exc:
        print(f"[n8n] Webhook error for '{event}': {exc}")


# ── Convenience helpers ───────────────────────────────────────────────────────

async def lead_captured(tenant_name: str, lead_id: str, customer_name: str,
                         phone: str, intent: str, budget: str, area: str,
                         property_type: str, call_id: str) -> None:
    await trigger("lead", {
        "event":         "lead_captured",
        "business":      tenant_name,
        "lead_id":       lead_id,
        "customer_name": customer_name,
        "phone":         phone,
        "intent":        intent,
        "budget":        budget,
        "area":          area,
        "property_type": property_type,
        "call_id":       call_id,
    })


async def viewing_booked(tenant_name: str, viewing_id: str, customer_name: str,
                          phone: str, property_address: str,
                          viewing_date: str, viewing_time: str) -> None:
    await trigger("viewing", {
        "event":            "viewing_booked",
        "business":         tenant_name,
        "viewing_id":       viewing_id,
        "customer_name":    customer_name,
        "phone":            phone,
        "property_address": property_address,
        "viewing_date":     viewing_date,
        "viewing_time":     viewing_time,
    })


async def inquiry_logged(tenant_name: str, inquiry_id: str, customer_name: str,
                          phone: str, details: str) -> None:
    await trigger("inquiry", {
        "event":           "inquiry_logged",
        "business":        tenant_name,
        "inquiry_id":      inquiry_id,
        "customer_name":   customer_name,
        "phone":           phone,
        "inquiry_details": details,
    })


async def missed_call(tenant_name: str, phone: str, call_id: str) -> None:
    await trigger("missed-call", {
        "event":    "missed_call",
        "business": tenant_name,
        "phone":    phone,
        "call_id":  call_id,
    })


async def call_ended(tenant_name: str, phone: str, call_id: str,
                      duration: int, summary: str, recording_url: str) -> None:
    await trigger("call-ended", {
        "event":         "call_ended",
        "business":      tenant_name,
        "phone":         phone,
        "call_id":       call_id,
        "duration_secs": duration,
        "summary":       summary,
        "recording_url": recording_url,
    })
