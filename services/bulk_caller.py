"""
Bulk calling service.
Accepts a list of leads and calls them one by one automatically.
Tracks progress per campaign and supports pause/stop controls.

Call pacing: DELAY_BETWEEN_CALLS seconds between each call initiation.
Vapi handles each call independently in the background.
"""

import asyncio
import csv
import io
from typing import List

import vapi.client as vapi
import db.store as store
from config import settings

DELAY_BETWEEN_CALLS = 15   # seconds between call initiations (adjust as needed)


# ── CSV parsing ───────────────────────────────────────────────────────────────

def parse_csv(file_bytes: bytes) -> List[dict]:
    """
    Parse a CSV file into a list of lead dicts.

    Expected columns (all optional except phone_number):
      phone_number, name, area, budget, intent

    Example CSV:
      name,phone_number,area,budget,intent
      احمد علی,+923001234567,DHA Lahore,15000000,buy
      سارہ خان,+923009876543,Bahria Town,8000000,rent
    """
    text = file_bytes.decode("utf-8-sig").strip()
    reader = csv.DictReader(io.StringIO(text))

    leads = []
    for row in reader:
        phone = row.get("phone_number", "").strip()
        if not phone:
            continue
        if not phone.startswith("+"):
            phone = "+" + phone
        leads.append({
            "phone_number": phone,
            "name": row.get("name", "").strip(),
            "area": row.get("area", "").strip(),
            "budget": row.get("budget", "").strip(),
            "intent": row.get("intent", "buy").strip(),
        })
    return leads


def parse_json_leads(raw: list) -> List[dict]:
    """Validate and normalize a JSON array of leads."""
    leads = []
    for item in raw:
        phone = str(item.get("phone_number", "")).strip()
        if not phone:
            continue
        if not phone.startswith("+"):
            phone = "+" + phone
        leads.append({
            "phone_number": phone,
            "name": item.get("name", ""),
            "area": item.get("area", ""),
            "budget": str(item.get("budget", "")),
            "intent": item.get("intent", "buy"),
        })
    return leads


# ── Campaign runner ───────────────────────────────────────────────────────────

async def run_campaign(campaign_id: str) -> None:
    """
    Background task: iterates through campaign leads and dials each one.
    Respects pause/stop signals stored in the campaign status.
    """
    campaign = store.get_campaign(campaign_id)
    if not campaign:
        print(f"[Bulk] Campaign {campaign_id} not found")
        return

    print(f"[Bulk] Starting campaign {campaign_id} — {campaign.total} leads")

    for i, lead in enumerate(campaign.leads):
        # Re-fetch status to check for pause/stop
        fresh = store.get_campaign(campaign_id)
        if fresh and fresh.status == "stopped":
            print(f"[Bulk] Campaign {campaign_id} stopped by user")
            return
        if fresh and fresh.status == "paused":
            print(f"[Bulk] Campaign {campaign_id} paused — waiting...")
            while True:
                await asyncio.sleep(10)
                fresh = store.get_campaign(campaign_id)
                if fresh and fresh.status != "paused":
                    break
            if fresh and fresh.status == "stopped":
                return

        if lead.status != "pending":
            continue   # already processed (e.g. retry picked it up)

        phone = lead.phone_number
        print(f"[Bulk] [{i+1}/{campaign.total}] Calling {phone} ({lead.name})")

        try:
            call = await vapi.make_call(
                phone_number=phone,
                assistant_id=settings.vapi_assistant_id,
                metadata={
                    "campaign_id": campaign_id,
                    "lead_name": lead.name,
                    "lead_area": lead.area,
                    "lead_budget": lead.budget,
                    "lead_intent": lead.intent,
                },
            )
            call_id = call.get("id", "")
            store.update_campaign_called(campaign_id, phone, call_id)
            print(f"[Bulk] Call placed: {call_id}")
        except Exception as exc:
            print(f"[Bulk] Failed to call {phone}: {exc}")
            store.update_campaign_failed(campaign_id, phone)

        # Pace the calls — wait before dialling the next number
        if i < campaign.total - 1:
            await asyncio.sleep(DELAY_BETWEEN_CALLS)

    store.set_campaign_status(campaign_id, "completed")
    print(f"[Bulk] Campaign {campaign_id} completed")
