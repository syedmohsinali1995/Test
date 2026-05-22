"""
Multi-tenant webhook handler.
Each tenant gets their own webhook URLs:
  POST /webhook/vapi/{tenant_id}   — lifecycle events
  POST /webhook/tool/{tenant_id}   — AI tool calls
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime
import asyncio

from db.database import SessionLocal
from db.models import Tenant, Lead, PropertyViewing, Inquiry, CallLog, Campaign, CampaignLead
from services.knowledge_base import search_properties
import services.n8n as n8n

_MISSED = {"no-answer", "busy", "failed", "canceled"}


def _get_tenant(tenant_id: str) -> Tenant | None:
    db = SessionLocal()
    try:
        return db.query(Tenant).filter(Tenant.id == tenant_id, Tenant.is_active == True).first()
    finally:
        db.close()


# ── Lifecycle events ──────────────────────────────────────────────────────────

async def handle_vapi_event(tenant_id: str, request: Request) -> JSONResponse:
    body    = await request.json()
    message = body.get("message", {})
    event   = message.get("type", "")

    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            return JSONResponse({"error": "tenant not found"}, status_code=404)

        if event == "call-started":
            _on_started(message, tenant, db)
        elif event == "end-of-call-report":
            _on_ended(message, tenant, db)
        elif event == "transcript":
            _on_transcript(message)
    finally:
        db.close()

    return JSONResponse({"status": "ok"})


def _on_started(message: dict, tenant: Tenant, db: Session):
    call        = message.get("call", {})
    call_id     = call.get("id", "")
    phone       = call.get("customer", {}).get("number", "")
    campaign_id = call.get("metadata", {}).get("campaign_id", "")

    log = CallLog(tenant_id=tenant.id, call_id=call_id,
                  phone_number=phone, campaign_id=campaign_id)
    db.add(log)
    db.commit()
    print(f"[{tenant.business_name}] Call started: {call_id} → {phone}")


def _on_ended(message: dict, tenant: Tenant, db: Session):
    call        = message.get("call", {})
    call_id     = call.get("id", "")
    end_reason  = call.get("endedReason", "")
    duration    = int(message.get("durationSeconds", 0))
    transcript  = message.get("transcript", "")
    recording   = message.get("recordingUrl", "")
    summary     = message.get("summary", "")
    phone       = call.get("customer", {}).get("number", "")
    is_missed   = end_reason in _MISSED or duration < 5

    log = db.query(CallLog).filter(CallLog.call_id == call_id).first()
    if log:
        log.duration_seconds = duration
        log.transcript       = transcript
        log.recording_url    = recording
        log.summary          = summary
        log.status           = "missed" if is_missed else "completed"
        log.ended_at         = datetime.utcnow()
        db.commit()

    if is_missed:
        _send_missed_whatsapp(tenant, phone)
        asyncio.create_task(n8n.missed_call(tenant.business_name, phone, call_id))
    else:
        asyncio.create_task(n8n.call_ended(tenant.business_name, phone, call_id, duration, summary, recording))

    print(f"[{tenant.business_name}] Call ended: {call_id}  {duration}s  {end_reason}")


def _on_transcript(message: dict):
    role = message.get("role", "")
    text = message.get("transcript", "")
    if text:
        print(f"[Transcript] {role}: {text}")


# ── Tool calls ────────────────────────────────────────────────────────────────

async def handle_tool_call(tenant_id: str, request: Request) -> JSONResponse:
    body        = await request.json()
    message     = body.get("message", {})
    tool_calls  = message.get("toolCalls", [])
    call_meta   = message.get("call", {})
    call_id     = call_meta.get("id", "")
    caller_phone = call_meta.get("customer", {}).get("number", "")
    campaign_id = call_meta.get("metadata", {}).get("campaign_id", "")

    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            return JSONResponse({"error": "tenant not found"}, status_code=404)

        results = []
        for tc in tool_calls:
            fn_name = tc.get("function", {}).get("name", "")
            args    = tc.get("function", {}).get("arguments", {})
            tool_id = tc.get("id", "")

            if fn_name == "search_properties":
                result = _tool_search(args, tenant)
            elif fn_name == "book_viewing":
                result = _tool_book_viewing(args, call_id, caller_phone, campaign_id, tenant, db)
            elif fn_name == "save_lead":
                result = _tool_save_lead(args, call_id, caller_phone, campaign_id, tenant, db)
            elif fn_name == "log_inquiry":
                result = _tool_log_inquiry(args, call_id, caller_phone, tenant, db)
            elif fn_name == "transfer_to_agent":
                result = {"success": True, "message": "ٹھیک ہے، میں آپ کو ہمارے سینیئر ایجنٹ سے ملاتی ہوں۔"}
            else:
                result = {"error": f"Unknown tool: {fn_name}"}

            results.append({"toolCallId": tool_id, "result": result})
    finally:
        db.close()

    return JSONResponse({"results": results})


def _tool_search(args: dict, tenant: Tenant) -> dict:
    return search_properties(
        city=args.get("city", ""), area=args.get("area", ""),
        intent=args.get("intent", ""), property_type=args.get("property_type", "any"),
        bedrooms=int(args.get("bedrooms", 0)), max_budget=int(args.get("max_budget", 0)),
        min_budget=int(args.get("min_budget", 0)),
    )


def _tool_book_viewing(args, call_id, caller_phone, campaign_id, tenant: Tenant, db: Session) -> dict:
    phone = args.get("phone_number") or caller_phone
    row = PropertyViewing(
        tenant_id=tenant.id, call_id=call_id, campaign_id=campaign_id,
        customer_name=args.get("customer_name", ""), phone_number=phone,
        property_address=args.get("property_address", ""),
        viewing_date=args.get("viewing_date", ""), viewing_time=args.get("viewing_time", ""),
        property_type=args.get("property_type", "house"),
    )
    db.add(row)
    if campaign_id:
        c = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if c:
            c.viewings_booked += 1
    db.commit()

    _send_whatsapp(tenant, phone, "viewing", row.id, args)
    asyncio.create_task(n8n.viewing_booked(
        tenant.business_name, row.id,
        args.get("customer_name", ""), phone,
        args.get("property_address", ""),
        args.get("viewing_date", ""), args.get("viewing_time", ""),
    ))
    return {
        "success": True, "viewing_id": row.id,
        "message": f"ملاقات {args.get('viewing_date')} کو {args.get('viewing_time')} بجے بک ہو گئی۔ نمبر {row.id}۔ واٹس ایپ تصدیق بھیج دی گئی ہے۔",
    }


def _tool_save_lead(args, call_id, caller_phone, campaign_id, tenant: Tenant, db: Session) -> dict:
    phone = args.get("phone_number") or caller_phone
    row = Lead(
        tenant_id=tenant.id, call_id=call_id, campaign_id=campaign_id,
        customer_name=args.get("customer_name", ""), phone_number=phone,
        intent=args.get("intent", "buy"), budget=args.get("budget", ""),
        preferred_area=args.get("preferred_area", ""), bedrooms=args.get("bedrooms", ""),
        timeline=args.get("timeline", ""), property_type=args.get("property_type", "any"),
    )
    db.add(row)
    if campaign_id:
        c = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if c:
            c.leads_saved += 1
    db.commit()

    _send_whatsapp(tenant, phone, "lead", row.id, args)
    asyncio.create_task(n8n.lead_captured(
        tenant.business_name, row.id,
        args.get("customer_name", ""), phone,
        args.get("intent", "buy"), args.get("budget", ""),
        args.get("preferred_area", ""), args.get("property_type", "any"),
        call_id,
    ))
    return {
        "success": True, "lead_id": row.id,
        "message": f"شکریہ {args.get('customer_name', '')}! لیڈ {row.id} محفوظ ہو گئی۔ ہمارا ایجنٹ جلد رابطہ کرے گا۔",
    }


def _tool_log_inquiry(args, call_id, caller_phone, tenant: Tenant, db: Session) -> dict:
    phone = args.get("phone_number") or caller_phone
    row = Inquiry(
        tenant_id=tenant.id, call_id=call_id,
        customer_name=args.get("customer_name", ""), phone_number=phone,
        inquiry_details=args.get("inquiry_details", ""),
    )
    db.add(row)
    db.commit()
    asyncio.create_task(n8n.inquiry_logged(
        tenant.business_name, row.id,
        args.get("customer_name", ""), phone,
        args.get("inquiry_details", ""),
    ))
    return {"success": True, "inquiry_id": row.id, "message": f"انکوائری {row.id} محفوظ ہو گئی۔"}


def _send_whatsapp(tenant: Tenant, phone: str, msg_type: str, record_id: str, args: dict):
    if not tenant.twilio_account_sid:
        return
    try:
        from twilio.rest import Client
        client = Client(tenant.twilio_account_sid, tenant.twilio_auth_token)
        if msg_type == "viewing":
            body = (f"السلام علیکم {args.get('customer_name', '')}! 🏠\n"
                    f"ملاقات کنفرم: {args.get('viewing_date')} {args.get('viewing_time')} بجے\n"
                    f"جائیداد: {args.get('property_address', '')}\n"
                    f"بکنگ نمبر: {record_id}\n— {tenant.business_name}")
        else:
            body = (f"السلام علیکم {args.get('customer_name', '')}! 👋\n"
                    f"آپ کی لیڈ {record_id} محفوظ ہو گئی۔\n"
                    f"ہمارا ایجنٹ جلد رابطہ کرے گا۔\n— {tenant.business_name}")

        client.messages.create(
            from_=tenant.twilio_whatsapp_number,
            to=f"whatsapp:{phone}", body=body,
        )
    except Exception as e:
        print(f"[WhatsApp] Error: {e}")


def _send_missed_whatsapp(tenant: Tenant, phone: str):
    if not tenant.twilio_account_sid or not phone:
        return
    try:
        from twilio.rest import Client
        client = Client(tenant.twilio_account_sid, tenant.twilio_auth_token)
        client.messages.create(
            from_=tenant.twilio_whatsapp_number,
            to=f"whatsapp:{phone}",
            body=f"السلام علیکم! {tenant.business_name} کی طرف سے کال کی گئی تھی۔ ہم جلد دوبارہ کوشش کریں گے۔",
        )
    except Exception as e:
        print(f"[WhatsApp] Missed call notice error: {e}")
