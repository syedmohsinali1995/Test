from twilio.rest import Client
from config import settings

_client = Client(settings.twilio_account_sid, settings.twilio_auth_token)


def make_outbound_call(to_number: str) -> str:
    """
    Initiate an outbound call to `to_number`.
    Twilio will fetch our /twiml endpoint when the call connects,
    which instructs it to open a Media Stream to our WebSocket server.
    Returns the Twilio Call SID.
    """
    twiml_url = f"{settings.public_url}/twiml"

    call = _client.calls.create(
        to=to_number,
        from_=settings.twilio_phone_number,
        url=twiml_url,
        method="POST",
    )

    print(f"[Twilio] Outbound call initiated: SID={call.sid} → {to_number}")
    return call.sid


def end_call(call_sid: str) -> None:
    """Hang up an active call."""
    _client.calls(call_sid).update(status="completed")
    print(f"[Twilio] Call ended: {call_sid}")


def get_call_status(call_sid: str) -> str:
    """Return the current status of a call (queued, ringing, in-progress, etc.)."""
    call = _client.calls(call_sid).fetch()
    return call.status
