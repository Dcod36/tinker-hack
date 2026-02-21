import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

# ── Twilio credentials (loaded from .env) ────────────────────────────────────
ACCOUNT_SID    = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN     = os.getenv("TWILIO_AUTH_TOKEN")
FROM_WHATSAPP  = os.getenv("TWILIO_FROM_WHATSAPP", "whatsapp:+14155238886")  # Twilio sandbox default
OFFICER_PHONE  = os.getenv("OFFICER_PHONE", "8589958840")   # contact number shown in message


def send_match_alert(
    complainant_phone: str,
    missing_name: str,
    match_distance: float,
    case_id: int = None,
) -> dict:
    """
    Send a WhatsApp alert to `complainant_phone` when a missing person is spotted.

    Args:
        complainant_phone : phone number of the complainant, e.g. '9876543210' or '+919876543210'
        missing_name      : name of the missing person
        match_distance    : cosine distance from the recognition result (lower = better)
        case_id           : optional case ID from the database

    Returns:
        dict with 'success' bool and 'sid' or 'error' keys.
    """
    if not ACCOUNT_SID or not AUTH_TOKEN:
        raise EnvironmentError(
            "TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN must be set in .env"
        )

    # Normalise phone → WhatsApp format
    to_number = _normalise_phone(complainant_phone)

    similarity_pct = max(0, round((1 - match_distance) * 100, 1))

    case_ref = f"Case #{case_id}" if case_id else "a reported case"

    message_body = (
        f"🚨 *Missing Person Alert*\n\n"
        f"A possible match has been found for *{missing_name}* "
        f"registered under {case_ref}.\n\n"
        f"📊 Match confidence: *{similarity_pct}%*\n\n"
        f"Please contact the officer immediately:\n"
        f"📞 *+91 {OFFICER_PHONE}*\n\n"
        f"— Missing Person AI System"
    )

    try:
        client = Client(ACCOUNT_SID, AUTH_TOKEN)
        message = client.messages.create(
            from_=FROM_WHATSAPP,
            to=to_number,
            body=message_body,
        )
        print(f"[WhatsApp] Message sent ✔  SID: {message.sid}  →  {to_number}")
        return {"success": True, "sid": message.sid}

    except Exception as e:
        print(f"[WhatsApp] Failed to send message: {e}")
        return {"success": False, "error": str(e)}


def _normalise_phone(phone: str) -> str:
    """
    Convert a raw phone number to 'whatsapp:+91XXXXXXXXXX' format.
    If already starts with '+', use as-is (just prepend whatsapp:).
    """
    phone = phone.strip().replace(" ", "").replace("-", "")
    if phone.startswith("whatsapp:"):
        return phone
    if phone.startswith("+"):
        return f"whatsapp:{phone}"
    if phone.startswith("91") and len(phone) == 12:
        return f"whatsapp:+{phone}"
    # assume Indian number
    return f"whatsapp:+91{phone}"
