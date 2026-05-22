"""Super-admin routes — only accessible with the admin JWT token."""

from fastapi import APIRouter, HTTPException, Depends, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from db.database import get_db
from db.models import Tenant
from auth.jwt_utils import hash_password, decode_token
import os

router = APIRouter(prefix="/admin", tags=["Admin"])

ADMIN_EMAIL = os.getenv("SUPER_ADMIN_EMAIL", "admin@yourdomain.com")


def _require_admin(authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    payload = decode_token(token)
    if not payload or payload.get("email") != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload


class CreateTenantRequest(BaseModel):
    business_name: str
    email: str
    password: str


@router.get("/tenants")
def list_tenants(db: Session = Depends(get_db), _=Depends(_require_admin)):
    tenants = db.query(Tenant).all()
    return [
        {
            "id": t.id,
            "business_name": t.business_name,
            "email": t.email,
            "is_active": t.is_active,
            "is_setup_complete": t.is_setup_complete,
            "created_at": t.created_at.isoformat(),
        }
        for t in tenants
    ]


@router.post("/tenants")
def create_tenant(body: CreateTenantRequest, db: Session = Depends(get_db), _=Depends(_require_admin)):
    if db.query(Tenant).filter(Tenant.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already exists")

    tenant = Tenant(
        business_name=body.business_name,
        email=body.email,
        password_hash=hash_password(body.password),
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return {"message": "Tenant created", "tenant_id": tenant.id, "email": tenant.email}


@router.patch("/tenants/{tenant_id}/toggle")
def toggle_tenant(tenant_id: str, db: Session = Depends(get_db), _=Depends(_require_admin)):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    tenant.is_active = not tenant.is_active
    db.commit()
    return {"tenant_id": tenant_id, "is_active": tenant.is_active}


@router.delete("/tenants/{tenant_id}")
def delete_tenant(tenant_id: str, db: Session = Depends(get_db), _=Depends(_require_admin)):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    db.delete(tenant)
    db.commit()
    return {"message": "Tenant deleted"}
