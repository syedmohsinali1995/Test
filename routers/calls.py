import asyncio
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
from db.database import get_db
from db.models import Tenant, Campaign, CampaignLead
from auth.jwt_utils import get_current_tenant
from services.bulk_caller import parse_csv, parse_json_leads
import httpx
from datetime import datetime

router = APIRouter(tags=["Calls"])

_VAPI_BASE = "https://api.vapi.ai"


def _headers(tenant: Tenant):
    return {"Authorization": f"Bearer {tenant.vapi_api_key}", "Content-Type": "application/json"}


def _check_ready(tenant: Tenant):
    if not tenant.vapi_api_key:
        raise HTTPException(status_code=400, detail="No Vapi API key found. Please complete the setup wizard.")
    if not tenant.vapi_assistant_id:
        raise HTTPException(status_code=400, detail="AI assistant not created yet. Please complete the setup wizard.")
    if not tenant.vapi_phone_number_id:
        raise HTTPException(status_code=400, detail="No phone number configured. Please complete the setup wizard.")


# ── Single Call ───────────────────────────────────────────────────────────────

class CallRequest(BaseModel):
    phone_number: str
    metadata: dict = {}


@router.post("/call")
async def make_call(body: CallRequest, tenant: Tenant = Depends(get_current_tenant)):
    _check_ready(tenant)
    if not body.phone_number.startswith("+"):
        raise HTTPException(status_code=400, detail="Use E.164 format: +923001234567")

    payload = {
        "assistantId": tenant.vapi_assistant_id,
        "customer": {"number": body.phone_number},
        "phoneNumberId": tenant.vapi_phone_number_id,
        "metadata": {**body.metadata, "tenant_id": tenant.id},
    }

    print(f"[Call] Dialing {body.phone_number} | assistant={tenant.vapi_assistant_id} | phone_id={tenant.vapi_phone_number_id}")

    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{_VAPI_BASE}/call/phone",
            json=payload,
            headers=_headers(tenant),
            timeout=30,
        )
        if not r.is_success:
            error_body = r.text
            print(f"[Vapi Call Error] {r.status_code}: {error_body}")
            raise HTTPException(
                status_code=400,
                detail=f"Vapi error ({r.status_code}): {error_body}"
            )
        call = r.json()

    return {"status": "calling", "call_id": call.get("id"), "phone_number": body.phone_number}


@router.get("/calls")
async def list_calls(limit: int = 20, tenant: Tenant = Depends(get_current_tenant)):
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{_VAPI_BASE}/call", params={"limit": limit}, headers=_headers(tenant), timeout=15)
        r.raise_for_status()
        return r.json()


@router.get("/call/{call_id}")
async def get_call(call_id: str, tenant: Tenant = Depends(get_current_tenant)):
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{_VAPI_BASE}/call/{call_id}", headers=_headers(tenant), timeout=15)
        r.raise_for_status()
        return r.json()


# ── Bulk Campaigns ────────────────────────────────────────────────────────────

class CampaignRequest(BaseModel):
    name: str
    leads: list


@router.post("/campaign/start")
async def start_campaign(
    body: CampaignRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    _check_ready(tenant)
    leads = parse_json_leads(body.leads)
    if not leads:
        raise HTTPException(status_code=400, detail="No valid phone numbers in leads list")

    campaign = _create_campaign(db, tenant.id, body.name, leads)
    asyncio.create_task(_run_campaign(campaign.id, tenant, db))
    return {"campaign_id": campaign.id, "total_leads": len(leads), "status": "running"}


@router.post("/campaign/upload-csv")
async def upload_csv(
    file: UploadFile = File(...),
    name: str = "CSV Campaign",
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    _check_ready(tenant)
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files accepted")
    content = await file.read()
    leads = parse_csv(content)
    if not leads:
        raise HTTPException(status_code=400, detail="No valid leads in CSV")

    campaign = _create_campaign(db, tenant.id, name, leads)
    asyncio.create_task(_run_campaign(campaign.id, tenant, db))
    return {"campaign_id": campaign.id, "total_leads": len(leads), "status": "running"}


@router.get("/campaigns")
def list_campaigns(tenant: Tenant = Depends(get_current_tenant), db: Session = Depends(get_db)):
    campaigns = db.query(Campaign).filter(Campaign.tenant_id == tenant.id).order_by(Campaign.created_at.desc()).all()
    return [_campaign_summary(c) for c in campaigns]


@router.get("/campaign/{campaign_id}")
def get_campaign(campaign_id: str, tenant: Tenant = Depends(get_current_tenant), db: Session = Depends(get_db)):
    c = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.tenant_id == tenant.id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return _campaign_summary(c)


@router.get("/campaign/{campaign_id}/leads")
def get_campaign_leads(campaign_id: str, tenant: Tenant = Depends(get_current_tenant), db: Session = Depends(get_db)):
    c = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.tenant_id == tenant.id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return [{"phone_number": l.phone_number, "name": l.name, "status": l.status, "call_id": l.call_id} for l in c.campaign_leads]


@router.post("/campaign/{campaign_id}/pause")
def pause_campaign(campaign_id: str, tenant: Tenant = Depends(get_current_tenant), db: Session = Depends(get_db)):
    return _set_status(campaign_id, tenant.id, "paused", db)


@router.post("/campaign/{campaign_id}/resume")
def resume_campaign(campaign_id: str, tenant: Tenant = Depends(get_current_tenant), db: Session = Depends(get_db)):
    return _set_status(campaign_id, tenant.id, "running", db)


@router.post("/campaign/{campaign_id}/stop")
def stop_campaign(campaign_id: str, tenant: Tenant = Depends(get_current_tenant), db: Session = Depends(get_db)):
    return _set_status(campaign_id, tenant.id, "stopped", db)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _create_campaign(db: Session, tenant_id: str, name: str, leads: list) -> Campaign:
    campaign = Campaign(tenant_id=tenant_id, name=name, total=len(leads))
    db.add(campaign)
    db.flush()
    for lead in leads:
        db.add(CampaignLead(
            campaign_id=campaign.id, tenant_id=tenant_id,
            phone_number=lead["phone_number"], name=lead.get("name", ""),
            area=lead.get("area", ""), budget=lead.get("budget", ""),
            intent=lead.get("intent", "buy"),
        ))
    db.commit()
    db.refresh(campaign)
    return campaign


def _campaign_summary(c: Campaign) -> dict:
    progress = round((c.called / c.total) * 100) if c.total else 0
    return {
        "id": c.id, "name": c.name, "total": c.total, "called": c.called,
        "failed": c.failed, "leads_saved": c.leads_saved, "viewings_booked": c.viewings_booked,
        "status": c.status, "progress_pct": progress,
        "created_at": c.created_at.isoformat(),
        "completed_at": c.completed_at.isoformat() if c.completed_at else None,
    }


def _set_status(campaign_id: str, tenant_id: str, status: str, db: Session) -> dict:
    c = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.tenant_id == tenant_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")
    c.status = status
    if status == "completed":
        c.completed_at = datetime.utcnow()
    db.commit()
    return {"campaign_id": campaign_id, "status": status}


async def _run_campaign(campaign_id: str, tenant: Tenant, db: Session):
    from db.database import SessionLocal
    DELAY = 15

    session = SessionLocal()
    try:
        campaign = session.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            return

        for i, lead in enumerate(campaign.campaign_leads):
            # Check for pause/stop
            session.refresh(campaign)
            while campaign.status == "paused":
                await asyncio.sleep(10)
                session.refresh(campaign)
            if campaign.status == "stopped":
                return

            if lead.status != "pending":
                continue

            try:
                payload = {
                    "assistantId": tenant.vapi_assistant_id,
                    "customer": {"number": lead.phone_number},
                    "phoneNumberId": tenant.vapi_phone_number_id,
                    "metadata": {"tenant_id": tenant.id, "campaign_id": campaign_id, "lead_name": lead.name},
                }
                async with httpx.AsyncClient() as client:
                    r = await client.post(
                        "https://api.vapi.ai/call/phone", json=payload,
                        headers={"Authorization": f"Bearer {tenant.vapi_api_key}"},
                        timeout=30,
                    )
                    r.raise_for_status()
                    call_id = r.json().get("id", "")

                lead.status  = "called"
                lead.call_id = call_id
                campaign.called += 1
                session.commit()
                print(f"[Campaign {campaign_id}] Called {lead.phone_number} → {call_id}")
            except Exception as exc:
                lead.status = "failed"
                campaign.failed += 1
                session.commit()
                print(f"[Campaign {campaign_id}] Failed {lead.phone_number}: {exc}")

            if i < campaign.total - 1:
                await asyncio.sleep(DELAY)

        campaign.status       = "completed"
        campaign.completed_at = datetime.utcnow()
        session.commit()
        print(f"[Campaign {campaign_id}] Completed")
    finally:
        session.close()
