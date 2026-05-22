"""
In-memory data store for the Urdu Real Estate Calling Agent.
Stores: property viewings, qualified leads, inquiries, and call logs.
Replace with a real database (PostgreSQL, MongoDB) for production.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict


def _now() -> str:
    return datetime.utcnow().isoformat()


# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class PropertyViewing:
    id: str
    customer_name: str
    phone_number: str
    property_address: str
    viewing_date: str
    viewing_time: str
    property_type: str
    call_id: str
    created_at: str = field(default_factory=_now)
    status: str = "scheduled"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Lead:
    id: str
    customer_name: str
    phone_number: str
    intent: str             # buy / rent / sell / invest
    budget: str
    preferred_area: str
    bedrooms: str
    timeline: str
    property_type: str
    call_id: str
    created_at: str = field(default_factory=_now)
    status: str = "new"     # new / contacted / converted / lost

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Inquiry:
    id: str
    customer_name: str
    phone_number: str
    inquiry_details: str
    call_id: str
    created_at: str = field(default_factory=_now)
    status: str = "open"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CallLog:
    call_id: str
    phone_number: str
    started_at: str
    ended_at: Optional[str] = None
    duration_seconds: Optional[int] = None
    transcript: Optional[str] = None
    recording_url: Optional[str] = None
    summary: Optional[str] = None
    status: str = "in-progress"

    def to_dict(self) -> dict:
        return asdict(self)


# ── In-memory storage ─────────────────────────────────────────────────────────

_viewings: Dict[str, PropertyViewing] = {}
_leads: Dict[str, Lead] = {}
_inquiries: Dict[str, Inquiry] = {}
_call_logs: Dict[str, CallLog] = {}


# ── Property Viewings ─────────────────────────────────────────────────────────

def create_viewing(
    customer_name: str,
    phone_number: str,
    property_address: str,
    viewing_date: str,
    viewing_time: str,
    call_id: str,
    property_type: str = "house",
) -> PropertyViewing:
    viewing = PropertyViewing(
        id=f"VW-{str(uuid.uuid4())[:6].upper()}",
        customer_name=customer_name,
        phone_number=phone_number,
        property_address=property_address,
        viewing_date=viewing_date,
        viewing_time=viewing_time,
        property_type=property_type,
        call_id=call_id,
    )
    _viewings[viewing.id] = viewing
    return viewing


def get_all_viewings() -> List[dict]:
    return [v.to_dict() for v in _viewings.values()]


# ── Leads ─────────────────────────────────────────────────────────────────────

def create_lead(
    customer_name: str,
    phone_number: str,
    intent: str,
    budget: str,
    preferred_area: str,
    call_id: str,
    bedrooms: str = "",
    timeline: str = "",
    property_type: str = "any",
) -> Lead:
    lead = Lead(
        id=f"LD-{str(uuid.uuid4())[:6].upper()}",
        customer_name=customer_name,
        phone_number=phone_number,
        intent=intent,
        budget=budget,
        preferred_area=preferred_area,
        bedrooms=bedrooms,
        timeline=timeline,
        property_type=property_type,
        call_id=call_id,
    )
    _leads[lead.id] = lead
    return lead


def get_all_leads() -> List[dict]:
    return [l.to_dict() for l in _leads.values()]


# ── Inquiries ─────────────────────────────────────────────────────────────────

def create_inquiry(
    customer_name: str,
    phone_number: str,
    inquiry_details: str,
    call_id: str,
) -> Inquiry:
    inquiry = Inquiry(
        id=f"INQ-{str(uuid.uuid4())[:6].upper()}",
        customer_name=customer_name,
        phone_number=phone_number,
        inquiry_details=inquiry_details,
        call_id=call_id,
    )
    _inquiries[inquiry.id] = inquiry
    return inquiry


def get_all_inquiries() -> List[dict]:
    return [i.to_dict() for i in _inquiries.values()]


# ── Call Logs ─────────────────────────────────────────────────────────────────

def log_call_start(call_id: str, phone_number: str) -> CallLog:
    log = CallLog(
        call_id=call_id,
        phone_number=phone_number,
        started_at=_now(),
    )
    _call_logs[call_id] = log
    return log


def update_call_end(
    call_id: str,
    duration_seconds: int,
    transcript: str = "",
    recording_url: str = "",
    summary: str = "",
    status: str = "completed",
) -> CallLog:
    log = _call_logs.get(call_id)
    if not log:
        log = CallLog(call_id=call_id, phone_number="unknown", started_at=_now())
        _call_logs[call_id] = log

    log.ended_at = _now()
    log.duration_seconds = duration_seconds
    log.transcript = transcript
    log.recording_url = recording_url
    log.summary = summary
    log.status = status
    return log


def get_all_call_logs() -> List[dict]:
    return [c.to_dict() for c in _call_logs.values()]


# ── Missed Calls ──────────────────────────────────────────────────────────────

@dataclass
class MissedCall:
    call_id: str
    phone_number: str
    attempted_at: str = field(default_factory=_now)
    retry_count: int = 0
    resolved: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


_missed_calls: Dict[str, MissedCall] = {}


def log_missed_call(call_id: str, phone_number: str) -> MissedCall:
    missed = _missed_calls.get(phone_number)
    if missed:
        missed.retry_count += 1
        missed.attempted_at = _now()
        missed.call_id = call_id
    else:
        missed = MissedCall(call_id=call_id, phone_number=phone_number)
        _missed_calls[phone_number] = missed
    return missed


def resolve_missed_call(phone_number: str) -> None:
    if phone_number in _missed_calls:
        _missed_calls[phone_number].resolved = True


def get_all_missed_calls() -> List[dict]:
    return [m.to_dict() for m in _missed_calls.values()]


# ── Bulk Call Campaigns ───────────────────────────────────────────────────────

@dataclass
class CampaignLead:
    phone_number: str
    name: str = ""
    area: str = ""
    budget: str = ""
    intent: str = ""
    status: str = "pending"   # pending / called / failed
    call_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Campaign:
    id: str
    name: str
    total: int
    called: int = 0
    answered: int = 0
    failed: int = 0
    leads_saved: int = 0
    viewings_booked: int = 0
    status: str = "running"   # running / paused / stopped / completed
    created_at: str = field(default_factory=_now)
    completed_at: str = ""
    leads: List[CampaignLead] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["progress_pct"] = round((self.called / self.total) * 100) if self.total else 0
        return d

    def summary(self) -> dict:
        """Lightweight summary without the full leads list."""
        return {
            "id": self.id,
            "name": self.name,
            "total": self.total,
            "called": self.called,
            "answered": self.answered,
            "failed": self.failed,
            "leads_saved": self.leads_saved,
            "viewings_booked": self.viewings_booked,
            "status": self.status,
            "progress_pct": round((self.called / self.total) * 100) if self.total else 0,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


_campaigns: Dict[str, Campaign] = {}


def create_campaign(name: str, leads: List[dict]) -> Campaign:
    campaign = Campaign(
        id=f"CAMP-{str(uuid.uuid4())[:6].upper()}",
        name=name,
        total=len(leads),
        leads=[
            CampaignLead(
                phone_number=l.get("phone_number", ""),
                name=l.get("name", ""),
                area=l.get("area", ""),
                budget=l.get("budget", ""),
                intent=l.get("intent", "buy"),
            )
            for l in leads
        ],
    )
    _campaigns[campaign.id] = campaign
    return campaign


def get_campaign(campaign_id: str) -> Optional[Campaign]:
    return _campaigns.get(campaign_id)


def get_all_campaigns() -> List[dict]:
    return [c.summary() for c in _campaigns.values()]


def update_campaign_called(campaign_id: str, phone_number: str, call_id: str) -> None:
    c = _campaigns.get(campaign_id)
    if not c:
        return
    c.called += 1
    for lead in c.leads:
        if lead.phone_number == phone_number:
            lead.status = "called"
            lead.call_id = call_id
            break


def update_campaign_failed(campaign_id: str, phone_number: str) -> None:
    c = _campaigns.get(campaign_id)
    if not c:
        return
    c.failed += 1
    for lead in c.leads:
        if lead.phone_number == phone_number:
            lead.status = "failed"
            break


def increment_campaign_leads(campaign_id: str) -> None:
    c = _campaigns.get(campaign_id)
    if c:
        c.leads_saved += 1


def increment_campaign_viewings(campaign_id: str) -> None:
    c = _campaigns.get(campaign_id)
    if c:
        c.viewings_booked += 1


def set_campaign_status(campaign_id: str, status: str) -> None:
    c = _campaigns.get(campaign_id)
    if c:
        c.status = status
        if status == "completed":
            c.completed_at = _now()


def get_campaign_leads(campaign_id: str) -> List[dict]:
    c = _campaigns.get(campaign_id)
    return [l.to_dict() for l in c.leads] if c else []
