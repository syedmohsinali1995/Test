from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from db.database import get_db
from db.models import Tenant
from auth.jwt_utils import verify_password, create_token, hash_password
import os

router = APIRouter(prefix="/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    business_name: str
    email: str
    password: str


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    # Read env vars at request time (not module load time)
    admin_email    = os.environ.get("SUPER_ADMIN_EMAIL", "admin@yourdomain.com")
    admin_password = os.environ.get("SUPER_ADMIN_PASSWORD", "change-this-password")

    # Super admin login
    if body.email == admin_email and body.password == admin_password:
        return {
            "token": create_token("admin", admin_email),
            "role": "admin",
            "business_name": "Admin",
        }

    # Tenant login
    tenant = db.query(Tenant).filter(Tenant.email == body.email).first()
    if not tenant or not verify_password(body.password, tenant.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not tenant.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled. Contact support.")

    return {
        "token": create_token(tenant.id, tenant.email),
        "role": "tenant",
        "business_name": tenant.business_name,
        "is_setup_complete": tenant.is_setup_complete,
        "tenant_id": tenant.id,
    }


@router.post("/register")
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(Tenant).filter(Tenant.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    tenant = Tenant(
        business_name=body.business_name,
        email=body.email,
        password_hash=hash_password(body.password),
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    return {
        "message": "Account created. Please complete the setup wizard.",
        "token": create_token(tenant.id, tenant.email),
        "tenant_id": tenant.id,
        "is_setup_complete": False,
    }
