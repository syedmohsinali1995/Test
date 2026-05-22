"""
Missed call retry service.
When an outbound call goes unanswered, this module:
  1. Logs it as a missed call
  2. Schedules automatic retries (up to MAX_RETRIES times)
  3. Sends a WhatsApp notification on first miss
  4. Runs as a background asyncio task checking every RETRY_INTERVAL_MINUTES
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict
from config import settings

MAX_RETRIES = 3
RETRY_INTERVAL_MINUTES = 30   # wait 30 min between retries

# In-memory retry queue: phone_number → retry state
_retry_queue: Dict[str, dict] = {}


def schedule_retry(phone_number: str, call_id: str, assistant_id: str) -> None:
    """Queue a missed call for retry."""
    if phone_number in _retry_queue:
        existing = _retry_queue[phone_number]
        if existing["attempts"] >= MAX_RETRIES:
            print(f"[Retry] Max retries reached for {phone_number}, skipping")
            return
        existing["attempts"] += 1
        existing["next_retry"] = _next_retry_time()
        print(f"[Retry] Re-queued {phone_number} — attempt {existing['attempts']}/{MAX_RETRIES}")
    else:
        _retry_queue[phone_number] = {
            "phone_number": phone_number,
            "last_call_id": call_id,
            "assistant_id": assistant_id,
            "attempts": 1,
            "next_retry": _next_retry_time(),
            "created_at": datetime.utcnow().isoformat(),
        }
        print(f"[Retry] Queued {phone_number} for first retry in {RETRY_INTERVAL_MINUTES} min")


def cancel_retry(phone_number: str) -> None:
    """Remove from retry queue (e.g. customer called back)."""
    if phone_number in _retry_queue:
        del _retry_queue[phone_number]
        print(f"[Retry] Cancelled retry for {phone_number}")


def get_retry_queue() -> list:
    return list(_retry_queue.values())


def _next_retry_time() -> str:
    return (datetime.utcnow() + timedelta(minutes=RETRY_INTERVAL_MINUTES)).isoformat()


async def start_retry_worker() -> None:
    """
    Background asyncio task — runs forever, checking the retry queue
    every minute and firing retries when their time has come.
    """
    print(f"[Retry Worker] Started — checking every 60 seconds")
    while True:
        await asyncio.sleep(60)
        await _process_due_retries()


async def _process_due_retries() -> None:
    now = datetime.utcnow()
    due = [
        entry for entry in list(_retry_queue.values())
        if datetime.fromisoformat(entry["next_retry"]) <= now
    ]

    for entry in due:
        phone = entry["phone_number"]
        attempt = entry["attempts"]
        print(f"[Retry] Firing retry call to {phone} (attempt {attempt}/{MAX_RETRIES})")

        try:
            import vapi.client as vapi
            call = await vapi.make_call(
                phone_number=phone,
                assistant_id=entry["assistant_id"] or settings.vapi_assistant_id,
                metadata={"retry_attempt": attempt},
            )
            entry["last_call_id"] = call.get("id", "")
            print(f"[Retry] Call placed: {call.get('id')}")
        except Exception as exc:
            print(f"[Retry] Failed to place retry call to {phone}: {exc}")

        # Schedule next retry or remove if max reached
        if attempt >= MAX_RETRIES:
            print(f"[Retry] Max retries ({MAX_RETRIES}) reached for {phone}. Removing.")
            del _retry_queue[phone]
        else:
            entry["attempts"] += 1
            entry["next_retry"] = _next_retry_time()
