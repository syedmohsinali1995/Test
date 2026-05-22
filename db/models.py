import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from db.database import Base


def _uid():
    return str(uuid.uuid4())


def _short_uid(prefix=""):
    return f"{prefix}{str(uuid.uuid4())[:6].upper()}"


# ── Tenant (one per real estate company) ─────────────────────────────────────

class Tenant(Base):
    __tablename__ = "tenants"

    id              = Column(String, primary_key=True, default=_uid)
    business_name   = Column(String, nullable=False)
    email           = Column(String, unique=True, nullable=False)
    password_hash   = Column(String, nullable=False)

    # API keys (filled during setup wizard)
    vapi_api_key            = Column(String, default="")
    vapi_phone_number_id    = Column(String, default="")
    vapi_assistant_id       = Column(String, default="")
    anthropic_api_key       = Column(String, default="")
    twilio_account_sid      = Column(String, default="")
    twilio_auth_token       = Column(String, default="")
    twilio_whatsapp_number  = Column(String, default="whatsapp:+14155238886")

    business_hours    = Column(String, default="پیر سے ہفتہ، صبح 9 بجے سے شام 6 بجے تک")
    is_active         = Column(Boolean, default=True)
    is_setup_complete = Column(Boolean, default=False)
    created_at        = Column(DateTime, default=datetime.utcnow)

    campaigns = relationship("Campaign",        back_populates="tenant", cascade="all, delete")
    leads     = relationship("Lead",            back_populates="tenant", cascade="all, delete")
    viewings  = relationship("PropertyViewing", back_populates="tenant", cascade="all, delete")
    inquiries = relationship("Inquiry",         back_populates="tenant", cascade="all, delete")
    call_logs = relationship("CallLog",         back_populates="tenant", cascade="all, delete")


# ── Campaign ──────────────────────────────────────────────────────────────────

class Campaign(Base):
    __tablename__ = "campaigns"

    id              = Column(String, primary_key=True, default=lambda: _short_uid("CAMP-"))
    tenant_id       = Column(String, ForeignKey("tenants.id"), nullable=False)
    name            = Column(String, nullable=False)
    total           = Column(Integer, default=0)
    called          = Column(Integer, default=0)
    failed          = Column(Integer, default=0)
    leads_saved     = Column(Integer, default=0)
    viewings_booked = Column(Integer, default=0)
    status          = Column(String, default="running")   # running/paused/stopped/completed
    created_at      = Column(DateTime, default=datetime.utcnow)
    completed_at    = Column(DateTime, nullable=True)

    tenant         = relationship("Tenant",       back_populates="campaigns")
    campaign_leads = relationship("CampaignLead", back_populates="campaign", cascade="all, delete")


class CampaignLead(Base):
    __tablename__ = "campaign_leads"

    id           = Column(String, primary_key=True, default=_uid)
    campaign_id  = Column(String, ForeignKey("campaigns.id"), nullable=False)
    tenant_id    = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)
    name         = Column(String, default="")
    area         = Column(String, default="")
    budget       = Column(String, default="")
    intent       = Column(String, default="buy")
    status       = Column(String, default="pending")  # pending/called/failed
    call_id      = Column(String, default="")

    campaign = relationship("Campaign", back_populates="campaign_leads")


# ── Lead ──────────────────────────────────────────────────────────────────────

class Lead(Base):
    __tablename__ = "leads"

    id             = Column(String, primary_key=True, default=lambda: _short_uid("LD-"))
    tenant_id      = Column(String, ForeignKey("tenants.id"), nullable=False)
    call_id        = Column(String, default="")
    campaign_id    = Column(String, default="")
    customer_name  = Column(String, default="")
    phone_number   = Column(String, default="")
    intent         = Column(String, default="buy")
    budget         = Column(String, default="")
    preferred_area = Column(String, default="")
    bedrooms       = Column(String, default="")
    timeline       = Column(String, default="")
    property_type  = Column(String, default="any")
    status         = Column(String, default="new")
    created_at     = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="leads")


# ── Property Viewing ──────────────────────────────────────────────────────────

class PropertyViewing(Base):
    __tablename__ = "viewings"

    id               = Column(String, primary_key=True, default=lambda: _short_uid("VW-"))
    tenant_id        = Column(String, ForeignKey("tenants.id"), nullable=False)
    call_id          = Column(String, default="")
    campaign_id      = Column(String, default="")
    customer_name    = Column(String, default="")
    phone_number     = Column(String, default="")
    property_address = Column(String, default="")
    viewing_date     = Column(String, default="")
    viewing_time     = Column(String, default="")
    property_type    = Column(String, default="house")
    status           = Column(String, default="scheduled")
    created_at       = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="viewings")


# ── Inquiry ───────────────────────────────────────────────────────────────────

class Inquiry(Base):
    __tablename__ = "inquiries"

    id               = Column(String, primary_key=True, default=lambda: _short_uid("INQ-"))
    tenant_id        = Column(String, ForeignKey("tenants.id"), nullable=False)
    call_id          = Column(String, default="")
    customer_name    = Column(String, default="")
    phone_number     = Column(String, default="")
    inquiry_details  = Column(Text, default="")
    status           = Column(String, default="open")
    created_at       = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="inquiries")


# ── Call Log ──────────────────────────────────────────────────────────────────

class CallLog(Base):
    __tablename__ = "call_logs"

    id               = Column(String, primary_key=True, default=_uid)
    tenant_id        = Column(String, ForeignKey("tenants.id"), nullable=False)
    call_id          = Column(String, default="")
    campaign_id      = Column(String, default="")
    phone_number     = Column(String, default="")
    duration_seconds = Column(Integer, default=0)
    transcript       = Column(Text, default="")
    recording_url    = Column(String, default="")
    summary          = Column(Text, default="")
    status           = Column(String, default="completed")
    started_at       = Column(DateTime, default=datetime.utcnow)
    ended_at         = Column(DateTime, nullable=True)

    tenant = relationship("Tenant", back_populates="call_logs")
