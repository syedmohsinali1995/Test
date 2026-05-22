from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from db.database import get_db
from db.models import Tenant, Lead, PropertyViewing, Inquiry, CallLog
from auth.jwt_utils import get_current_tenant

router = APIRouter(tags=["Records"])


@router.get("/leads")
def get_leads(tenant: Tenant = Depends(get_current_tenant), db: Session = Depends(get_db)):
    rows = db.query(Lead).filter(Lead.tenant_id == tenant.id).order_by(Lead.created_at.desc()).all()
    return [{"id": r.id, "customer_name": r.customer_name, "phone_number": r.phone_number,
             "intent": r.intent, "budget": r.budget, "preferred_area": r.preferred_area,
             "bedrooms": r.bedrooms, "property_type": r.property_type, "status": r.status,
             "created_at": r.created_at.isoformat()} for r in rows]


@router.get("/viewings")
def get_viewings(tenant: Tenant = Depends(get_current_tenant), db: Session = Depends(get_db)):
    rows = db.query(PropertyViewing).filter(PropertyViewing.tenant_id == tenant.id).order_by(PropertyViewing.created_at.desc()).all()
    return [{"id": r.id, "customer_name": r.customer_name, "phone_number": r.phone_number,
             "property_address": r.property_address, "viewing_date": r.viewing_date,
             "viewing_time": r.viewing_time, "property_type": r.property_type,
             "status": r.status, "created_at": r.created_at.isoformat()} for r in rows]


@router.get("/inquiries")
def get_inquiries(tenant: Tenant = Depends(get_current_tenant), db: Session = Depends(get_db)):
    rows = db.query(Inquiry).filter(Inquiry.tenant_id == tenant.id).order_by(Inquiry.created_at.desc()).all()
    return [{"id": r.id, "customer_name": r.customer_name, "phone_number": r.phone_number,
             "inquiry_details": r.inquiry_details, "status": r.status,
             "created_at": r.created_at.isoformat()} for r in rows]


@router.get("/call-logs")
def get_call_logs(tenant: Tenant = Depends(get_current_tenant), db: Session = Depends(get_db)):
    rows = db.query(CallLog).filter(CallLog.tenant_id == tenant.id).order_by(CallLog.started_at.desc()).all()
    return [{"id": r.id, "call_id": r.call_id, "phone_number": r.phone_number,
             "duration_seconds": r.duration_seconds, "status": r.status,
             "recording_url": r.recording_url, "summary": r.summary,
             "started_at": r.started_at.isoformat()} for r in rows]


@router.get("/stats")
def get_stats(tenant: Tenant = Depends(get_current_tenant), db: Session = Depends(get_db)):
    from db.models import Campaign
    return {
        "total_leads":     db.query(Lead).filter(Lead.tenant_id == tenant.id).count(),
        "total_viewings":  db.query(PropertyViewing).filter(PropertyViewing.tenant_id == tenant.id).count(),
        "total_inquiries": db.query(Inquiry).filter(Inquiry.tenant_id == tenant.id).count(),
        "total_calls":     db.query(CallLog).filter(CallLog.tenant_id == tenant.id).count(),
        "total_campaigns": db.query(Campaign).filter(Campaign.tenant_id == tenant.id).count(),
    }
